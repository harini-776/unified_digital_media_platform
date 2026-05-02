"""
Train Fusion Model.
Usage: python scripts/train_fusion.py --manifest data/manifest.json --config ml/configs/config.yaml
"""
from __future__ import annotations
import argparse, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json, yaml, numpy as np, torch, torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from tqdm import tqdm

from ml.models.fusion_model import FusionModel, ScoreOnlyFusion
from ml.training.losses import FocalLoss
from ml.training.trainer_utils import set_seed, EarlyStopping, save_checkpoint, compute_metrics
from ml.calibration.calibrator import TemperatureScaler


def load_expert_predictions(manifest_path, split, scores_cache):
    cache_file = os.path.join(scores_cache, f"expert_scores_{split}.npy")
    if not os.path.exists(cache_file):
        raise FileNotFoundError(
            f"Expert scores cache not found: {cache_file}\n"
            "Run: python scripts/extract_expert_scores.py --manifest data/manifest.json"
        )
    data = np.load(cache_file)
    return data[:, :5], data[:, 5].astype(int)


class FusionDataset(Dataset):
    def __init__(self, scores, labels, modality_dropout_prob=0.2):
        self.scores = torch.from_numpy(scores).float()
        self.labels = torch.from_numpy(labels).float()
        self.modality_dropout_prob = modality_dropout_prob

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        scores = self.scores[idx].clone()
        label  = self.labels[idx]
        if self.modality_dropout_prob > 0 and torch.rand(1).item() < self.modality_dropout_prob:
            zero_idx = torch.randint(0, 5, (1,)).item()
            scores[zero_idx] = 0.5
        return {"scores": scores, "label": label}


def build_score_dicts(batch_scores, device):
    keys = ["face", "lipsync", "voice", "blink", "headmotion"]
    return {k: batch_scores[:, i:i+1].to(device) for i, k in enumerate(keys)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest",     type=str, required=True)
    parser.add_argument("--config",       type=str, default="ml/configs/config.yaml")
    parser.add_argument("--scores_cache", type=str, default="data/expert_scores")
    parser.add_argument("--score_only",   action="store_true")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    fc = cfg["fusion"]
    set_seed(cfg["seed"])
    device = torch.device(cfg["device"] if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    X_train, y_train = load_expert_predictions(args.manifest, "train", args.scores_cache)
    X_val,   y_val   = load_expert_predictions(args.manifest, "val",   args.scores_cache)
    print(f"Train: {len(X_train)}  Val: {len(X_val)}")

    X_train_n = X_train / 100.0
    X_val_n   = X_val   / 100.0

    train_ds = FusionDataset(X_train_n, y_train, fc["modality_dropout_prob"])
    val_ds   = FusionDataset(X_val_n,   y_val,   0.0)
    train_loader = DataLoader(train_ds, batch_size=fc["batch_size"], shuffle=True,  num_workers=2)
    val_loader   = DataLoader(val_ds,   batch_size=fc["batch_size"], shuffle=False, num_workers=2)

    if args.score_only:
        model = ScoreOnlyFusion(hidden_dim=fc["hidden_dim"], dropout=fc["dropout"]).to(device)
    else:
        model = FusionModel(
            gate_out_dim=64, hidden_dim=fc["hidden_dim"], dropout=fc["dropout"],
            modality_dropout_prob=fc["modality_dropout_prob"],
            face_emb_dim=0, voice_emb_dim=0, lipsync_emb_dim=0,
        ).to(device)

    optimizer  = AdamW(model.parameters(), lr=fc["lr"], weight_decay=fc["weight_decay"])
    criterion  = FocalLoss(gamma=fc["focal_loss_gamma"], label_smoothing=fc["label_smoothing"])
    scheduler  = CosineAnnealingLR(optimizer, T_max=fc["epochs"])
    early_stop = EarlyStopping(patience=7, mode="max")

    os.makedirs(fc["checkpoint_dir"], exist_ok=True)
    best_auc = 0.0

    for epoch in range(fc["epochs"]):
        model.train()
        all_probs, all_labels = [], []

        for batch in tqdm(train_loader, desc=f"Epoch {epoch+1}"):
            scores = batch["scores"].to(device)
            labels = batch["label"].to(device)
            optimizer.zero_grad()
            out = model(scores) if args.score_only else model(build_score_dicts(scores, device))
            loss = criterion(out["logit"].squeeze(-1), labels)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            all_probs.extend(out["probability"].detach().cpu().tolist())
            all_labels.extend(labels.cpu().tolist())

        train_m = compute_metrics(all_probs, all_labels)
        model.eval()
        val_probs, val_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                scores = batch["scores"].to(device)
                out = model(scores) if args.score_only else model(build_score_dicts(scores, device))
                val_probs.extend(out["probability"].cpu().tolist())
                val_labels.extend(batch["label"].tolist())

        val_m = compute_metrics(val_probs, val_labels)
        scheduler.step()
        print(f"Ep{epoch+1} | Train auc={train_m['auc_roc']:.4f} | Val auc={val_m['auc_roc']:.4f} f1={val_m['f1']:.4f}")

        if val_m["auc_roc"] > best_auc:
            best_auc = val_m["auc_roc"]
            save_checkpoint(model, optimizer, epoch, best_auc, os.path.join(fc["checkpoint_dir"], "best.pt"))
            print(f"  ** Best AUC: {best_auc:.4f} **")

        if early_stop.step(val_m["auc_roc"]):
            print("Early stopping."); break

    # Temperature calibration
    print("\nCalibrating on val set...")
    model.eval()
    all_logits, all_labs = [], []
    with torch.no_grad():
        for batch in val_loader:
            scores = batch["scores"].to(device)
            out = model(scores) if args.score_only else model(build_score_dicts(scores, device))
            all_logits.append(out["logit"].cpu())
            all_labs.extend(batch["label"].tolist())

    logits_t = torch.cat(all_logits).squeeze(-1)
    labels_t = torch.tensor(all_labs)
    scaler = TemperatureScaler()
    T = scaler.fit(logits_t, labels_t)
    print(f"Optimal temperature: {T:.4f}")
    torch.save({"temperature": T}, os.path.join(fc["checkpoint_dir"], "temperature.pt"))
    print(f"\nDone. Best val AUC-ROC: {best_auc:.4f}")


if __name__ == "__main__":
    main()
