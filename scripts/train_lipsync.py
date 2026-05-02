"""
Train Lip-Sync Branch.

Trains a SyncNet-style audio-visual synchronization model.
Uses contrastive + BCE loss on (mouth_crop_sequence, mel_spectrogram) pairs.

Usage:
    python scripts/train_lipsync.py --manifest data/manifest.json
"""
from __future__ import annotations

import argparse, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json, yaml, subprocess, hashlib
import numpy as np, cv2
import torch, torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from tqdm import tqdm
import librosa

from ml.models.lipsync_model import LipSyncModel
from ml.training.losses import FocalLoss, ContrastiveLoss
from ml.training.trainer_utils import set_seed, EarlyStopping, save_checkpoint, compute_metrics

N_MELS = 80

def extract_audio(video_path, cache_dir):
    h = hashlib.md5(video_path.encode()).hexdigest()[:12]
    out = os.path.join(cache_dir, f"audio_{h}.wav")
    if os.path.exists(out):
        return out
    os.makedirs(cache_dir, exist_ok=True)
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
           "-ar", "16000", "-ac", "1", out, "-y", "-loglevel", "error"]
    r = subprocess.run(cmd, capture_output=True)
    return out if r.returncode == 0 and os.path.exists(out) else None


def get_mouth_crop(frame):
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, 1.3, 5)
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    mouth_y = y + int(h * 0.6)
    crop = frame[mouth_y: y + h, x: x + w]
    return cv2.resize(crop, (96, 64)) if crop.size > 0 else None


class LipSyncDataset(Dataset):
    def __init__(self, manifest_path, split, cache_dir, n_mouth_frames=16, target_fps=25.0):
        with open(manifest_path) as f:
            records = json.load(f)
        self.records = [r for r in records if r.get("split") == split]
        self.cache_dir = cache_dir
        self.n_frames = n_mouth_frames
        self.target_fps = target_fps
        self.sr = 16000

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        rec = self.records[idx]
        label = rec["label"]
        mouth_seq = self._get_mouth_sequence(rec["video_path"])
        mel = self._get_mel(rec["video_path"])
        if label == 1 and np.random.rand() > 0.5:
            shift = np.random.randint(self.n_frames // 2, self.n_frames)
            mel = np.roll(mel, shift, axis=-1)
        mouth_t = torch.from_numpy(mouth_seq).float() / 255.0
        mel_t = torch.from_numpy(mel[np.newaxis]).float()
        return {"mouth": mouth_t, "mel": mel_t, "label": torch.tensor(label, dtype=torch.float32)}

    def _get_mouth_sequence(self, video_path):
        h = hashlib.md5(video_path.encode()).hexdigest()[:12]
        cache_f = os.path.join(self.cache_dir, f"mouth_{h}.npy")
        if os.path.exists(cache_f):
            return np.load(cache_f)
        os.makedirs(self.cache_dir, exist_ok=True)
        cap = cv2.VideoCapture(video_path)
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(src_fps / self.target_fps))
        crops, fi = [], 0
        while cap.isOpened() and len(crops) < self.n_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if fi % step == 0:
                crop = get_mouth_crop(frame)
                if crop is not None:
                    crops.append(crop)
            fi += 1
        cap.release()
        blank = np.zeros((64, 96, 3), dtype=np.uint8)
        while len(crops) < self.n_frames:
            crops.append(blank)
        arr = np.stack(crops[:self.n_frames]).transpose(0, 3, 1, 2)
        np.save(cache_f, arr)
        return arr

    def _get_mel(self, video_path):
        audio_path = extract_audio(video_path, self.cache_dir)
        if audio_path is None:
            return np.zeros((N_MELS, 128), dtype=np.float32)
        try:
            wav, _ = librosa.load(audio_path, sr=self.sr, mono=True, duration=2.0)
        except Exception:
            return np.zeros((N_MELS, 128), dtype=np.float32)
        mel = librosa.feature.melspectrogram(y=wav, sr=self.sr, n_mels=N_MELS)
        mel_db = librosa.power_to_db(mel + 1e-6, ref=np.max)
        mel_db = (mel_db - mel_db.mean()) / (mel_db.std() + 1e-6)
        target_t = 128
        if mel_db.shape[1] >= target_t:
            mel_db = mel_db[:, :target_t]
        else:
            mel_db = np.pad(mel_db, ((0, 0), (0, target_t - mel_db.shape[1])))
        return mel_db.astype(np.float32)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=str, required=True)
    parser.add_argument("--config", type=str, default="ml/configs/config.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    lc = cfg["lipsync"]
    set_seed(cfg["seed"])
    device = torch.device(cfg["device"] if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    train_ds = LipSyncDataset(args.manifest, "train", cfg["data"]["cache_dir"])
    val_ds   = LipSyncDataset(args.manifest, "val",   cfg["data"]["cache_dir"])
    train_loader = DataLoader(train_ds, batch_size=lc["batch_size"], shuffle=True, num_workers=2)
    val_loader   = DataLoader(val_ds, batch_size=lc["batch_size"], shuffle=False, num_workers=2)

    model = LipSyncModel(embedding_dim=lc["embedding_dim"]).to(device)
    optimizer = AdamW(model.parameters(), lr=lc["lr"], weight_decay=lc["weight_decay"])
    bce_loss  = FocalLoss(gamma=2.0, label_smoothing=0.05)
    cont_loss = ContrastiveLoss(margin=1.0)
    scheduler = CosineAnnealingLR(optimizer, T_max=lc["epochs"])
    early_stop = EarlyStopping(patience=5, mode="max")

    os.makedirs(lc["checkpoint_dir"], exist_ok=True)
    best_auc = 0.0

    for epoch in range(lc["epochs"]):
        model.train()
        all_probs, all_labels = [], []
        for batch in tqdm(train_loader, desc=f"Epoch {epoch+1}"):
            mouth = batch["mouth"].to(device)
            mel   = batch["mel"].to(device)
            labels = batch["label"].to(device)
            optimizer.zero_grad()
            out = model(mel, mouth)
            loss = bce_loss(out["logit"].squeeze(-1), labels) + \
                   0.3 * cont_loss(out["audio_embedding"], out["video_embedding"], labels)
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
                out = model(batch["mel"].to(device), batch["mouth"].to(device))
                val_probs.extend(torch.sigmoid(out["logit"]).squeeze(-1).cpu().tolist())
                val_labels.extend(batch["label"].tolist())

        val_m = compute_metrics(val_probs, val_labels)
        scheduler.step()
        print(f"Ep{epoch+1} | Train auc={train_m['auc_roc']:.4f} | Val auc={val_m['auc_roc']:.4f}")

        if val_m["auc_roc"] > best_auc:
            best_auc = val_m["auc_roc"]
            save_checkpoint(model, optimizer, epoch, best_auc, os.path.join(lc["checkpoint_dir"], "best.pt"))
            print(f"  ** Best AUC: {best_auc:.4f} **")

        if early_stop.step(val_m["auc_roc"]):
            print("Early stopping.")
            break


if __name__ == "__main__":
    main()
