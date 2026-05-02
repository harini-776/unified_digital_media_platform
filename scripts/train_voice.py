"""
Train Voice Authenticity Branch.

Extracts wav2vec2 embeddings + MFCC features from audio files,
then trains the VoiceModel classifier.

Usage:
    python scripts/train_voice.py --manifest data/manifest.json --config ml/configs/config.yaml
"""
from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import yaml
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from tqdm import tqdm
import librosa

from ml.models.voice_model import VoiceModel, Wav2Vec2FeatureExtractor
from ml.training.losses import FocalLoss
from ml.training.trainer_utils import (
    set_seed, EarlyStopping, save_checkpoint, compute_metrics
)


def extract_audio_from_video(video_path: str, cache_dir: str) -> str | None:
    """Extract 16kHz mono WAV from video using ffmpeg."""
    import subprocess
    import hashlib
    h = hashlib.md5(video_path.encode()).hexdigest()[:12]
    audio_path = os.path.join(cache_dir, f"audio_{h}.wav")
    if os.path.exists(audio_path):
        return audio_path
    os.makedirs(cache_dir, exist_ok=True)
    cmd = [
        "ffmpeg", "-i", video_path, "-vn",
        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        audio_path, "-y", "-loglevel", "error",
    ]
    result = subprocess.run(cmd, capture_output=True)
    return audio_path if result.returncode == 0 and os.path.exists(audio_path) else None


class VoiceDataset(Dataset):
    """Dataset for voice branch training."""

    def __init__(
        self,
        manifest_path: str,
        split: str,
        w2v_extractor: Wav2Vec2FeatureExtractor,
        cache_dir: str,
        n_mfcc: int = 40,
        segment_sec: float = 3.0,
    ):
        with open(manifest_path) as f:
            records = json.load(f)
        self.records = [r for r in records if r.get("split") == split]
        self.w2v = w2v_extractor
        self.cache_dir = cache_dir
        self.n_mfcc = n_mfcc
        self.segment_sec = segment_sec
        self.sr = 16000

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        rec = self.records[idx]
        audio_path = extract_audio_from_video(rec["video_path"], self.cache_dir)

        zeros_w2v  = torch.zeros(768)
        zeros_mfcc = torch.zeros(self.n_mfcc, 128)
        label_t    = torch.tensor(rec["label"], dtype=torch.float32)

        if audio_path is None:
            return {"w2v": zeros_w2v, "mfcc": zeros_mfcc, "label": label_t}

        try:
            waveform, _ = librosa.load(audio_path, sr=self.sr, mono=True)
        except Exception:
            return {"w2v": zeros_w2v, "mfcc": zeros_mfcc, "label": label_t}

        seg_len = int(self.segment_sec * self.sr)
        if len(waveform) >= seg_len:
            waveform = waveform[:seg_len]
        else:
            waveform = np.pad(waveform, (0, seg_len - len(waveform)))

        w2v_emb = self.w2v.encode(waveform, self.sr)

        mfcc = librosa.feature.mfcc(y=waveform, sr=self.sr, n_mfcc=self.n_mfcc)
        target_t = 128
        if mfcc.shape[1] >= target_t:
            mfcc = mfcc[:, :target_t]
        else:
            mfcc = np.pad(mfcc, ((0, 0), (0, target_t - mfcc.shape[1])))

        return {
            "w2v": w2v_emb.float(),
            "mfcc": torch.from_numpy(mfcc).float(),
            "label": label_t,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=str, required=True)
    parser.add_argument("--config",   type=str, default="ml/configs/config.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    vc = cfg["voice"]
    set_seed(cfg["seed"])
    device = torch.device(cfg["device"] if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    w2v = Wav2Vec2FeatureExtractor(device=str(device))

    train_ds = VoiceDataset(args.manifest, "train", w2v, cfg["data"]["cache_dir"], segment_sec=vc["segment_sec"])
    val_ds   = VoiceDataset(args.manifest, "val",   w2v, cfg["data"]["cache_dir"], segment_sec=vc["segment_sec"])

    train_loader = DataLoader(train_ds, batch_size=vc["batch_size"], shuffle=True,  num_workers=2)
    val_loader   = DataLoader(val_ds,   batch_size=vc["batch_size"], shuffle=False, num_workers=2)

    model = VoiceModel(
        wav2vec2_dim=768,
        spectral_n_features=40,
        embedding_dim=vc["embedding_dim"],
    ).to(device)

    optimizer = AdamW(model.parameters(), lr=vc["lr"], weight_decay=vc["weight_decay"])
    criterion = FocalLoss(gamma=2.0, label_smoothing=0.05)
    scheduler = CosineAnnealingLR(optimizer, T_max=vc["epochs"])
    early_stop = EarlyStopping(patience=5, mode="max")

    os.makedirs(vc["checkpoint_dir"], exist_ok=True)
    best_auc = 0.0

    for epoch in range(vc["epochs"]):
        model.train()
        all_probs, all_labels = [], []

        for batch in tqdm(train_loader, desc=f"Epoch {epoch+1} Train"):
            w2v_emb = batch["w2v"].to(device)
            mfcc    = batch["mfcc"].to(device)
            labels  = batch["label"].to(device)

            optimizer.zero_grad()
            out  = model(w2v_emb, mfcc)
            loss = criterion(out["logit"].squeeze(-1), labels)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            all_probs.extend(torch.sigmoid(out["logit"].detach()).squeeze(-1).cpu().tolist())
            all_labels.extend(labels.cpu().tolist())

        train_m = compute_metrics(all_probs, all_labels)

        model.eval()
        val_probs, val_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                out = model(batch["w2v"].to(device), batch["mfcc"].to(device))
                val_probs.extend(torch.sigmoid(out["logit"]).squeeze(-1).cpu().tolist())
                val_labels.extend(batch["label"].tolist())

        val_m = compute_metrics(val_probs, val_labels)
        scheduler.step()

        print(f"Ep{epoch+1} | Train auc={train_m['auc_roc']:.4f} | Val auc={val_m['auc_roc']:.4f}")

        if val_m["auc_roc"] > best_auc:
            best_auc = val_m["auc_roc"]
            save_checkpoint(model, optimizer, epoch, best_auc, os.path.join(vc["checkpoint_dir"], "best.pt"))
            print(f"  ** Best AUC: {best_auc:.4f} **")

        if early_stop.step(val_m["auc_roc"]):
            print("Early stopping.")
            break


if __name__ == "__main__":
    main()
