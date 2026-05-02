"""
Train Face Artifact + Temporal Branch.

Usage:
    python scripts/train_face.py --manifest data/manifest.json --config ml/configs/config.yaml

Saves best checkpoint to weights/face/best.pt (by val ROC-AUC).
"""
from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from tqdm import tqdm

from ml.models.face_model import FaceTemporalModel
from ml.datasets.base_dataset import build_dataloader
from ml.training.losses import FocalLoss
from ml.training.trainer_utils import (
    set_seed, EarlyStopping, save_checkpoint, load_checkpoint, compute_metrics
)


def train_epoch(model, loader, optimizer, criterion, device) -> dict:
    model.train()
    total_loss = 0.0
    all_probs, all_labels = [], []

    for batch in tqdm(loader, desc="Train", leave=False):
        frames = batch["frames"].to(device)    # (B, T, C, H, W)
        labels = batch["label"].to(device)     # (B,)

        optimizer.zero_grad()
        out = model(frames)
        loss = criterion(out["logit"].squeeze(-1), labels)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        total_loss += loss.item()
        probs = torch.sigmoid(out["logit"].detach()).squeeze(-1).cpu().tolist()
        all_probs.extend(probs)
        all_labels.extend(labels.cpu().tolist())

    metrics = compute_metrics(all_probs, all_labels)
    metrics["loss"] = total_loss / len(loader)
    return metrics


@torch.no_grad()
def eval_epoch(model, loader, criterion, device) -> dict:
    model.eval()
    total_loss = 0.0
    all_probs, all_labels = [], []

    for batch in tqdm(loader, desc="Val", leave=False):
        frames = batch["frames"].to(device)
        labels = batch["label"].to(device)

        out = model(frames)
        loss = criterion(out["logit"].squeeze(-1), labels)
        total_loss += loss.item()

        probs = torch.sigmoid(out["logit"]).squeeze(-1).cpu().tolist()
        all_probs.extend(probs)
        all_labels.extend(labels.cpu().tolist())

    metrics = compute_metrics(all_probs, all_labels)
    metrics["loss"] = total_loss / len(loader)
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=str, required=True)
    parser.add_argument("--config",   type=str, default="ml/configs/config.yaml")
    parser.add_argument("--resume",   type=str, default=None)
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    fc = cfg["face"]
    set_seed(cfg["seed"])
    device = torch.device(cfg["device"] if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    common_kwargs = dict(
        num_frames=fc["num_frames_train"],
        face_size=cfg["data"]["face_size"],
        fps=cfg["data"]["target_fps"],
        cache_dir=cfg["data"]["cache_dir"],
    )
    train_loader = build_dataloader(
        args.manifest, "train", fc["batch_size"],
        augment=True, num_workers=cfg["num_workers"], **common_kwargs
    )
    val_loader = build_dataloader(
        args.manifest, "val", fc["batch_size"],
        augment=False, num_workers=cfg["num_workers"], **common_kwargs
    )

    model = FaceTemporalModel(
        backbone=fc["backbone"],
        temporal=fc["temporal"],
        embedding_dim=fc["embedding_dim"],
        num_heads=fc["temporal_heads"],
        num_layers=fc["temporal_layers"],
        dropout=fc["dropout"],
        pretrained=fc["pretrained"],
    ).to(device)

    optimizer = AdamW(model.parameters(), lr=fc["lr"], weight_decay=fc["weight_decay"])
    criterion = FocalLoss(
        gamma=fc["focal_loss_gamma"],
        label_smoothing=cfg["data"]["augmentations"]["label_smoothing"],
    )
    scheduler = CosineAnnealingLR(optimizer, T_max=fc["epochs"])
    early_stop = EarlyStopping(patience=7, mode="max")

    start_epoch = 0
    if args.resume:
        start_epoch, _ = load_checkpoint(args.resume, model, optimizer)
        print(f"Resumed from epoch {start_epoch}")

    os.makedirs(fc["checkpoint_dir"], exist_ok=True)
    best_auc = 0.0

    for epoch in range(start_epoch, fc["epochs"]):
        print(f"\nEpoch {epoch+1}/{fc['epochs']}")

        train_m = train_epoch(model, train_loader, optimizer, criterion, device)
        val_m   = eval_epoch(model, val_loader, criterion, device)
        scheduler.step()

        print(f"  Train | loss={train_m['loss']:.4f}  auc={train_m['auc_roc']:.4f}  f1={train_m['f1']:.4f}")
        print(f"  Val   | loss={val_m['loss']:.4f}    auc={val_m['auc_roc']:.4f}    f1={val_m['f1']:.4f}")

        if val_m["auc_roc"] > best_auc:
            best_auc = val_m["auc_roc"]
            save_checkpoint(
                model, optimizer, epoch, best_auc,
                os.path.join(fc["checkpoint_dir"], "best.pt"),
            )
            print(f"  ** New best AUC: {best_auc:.4f} — checkpoint saved **")

        if early_stop.step(val_m["auc_roc"]):
            print("Early stopping triggered.")
            break

    print(f"\nDone. Best val AUC-ROC: {best_auc:.4f}")


if __name__ == "__main__":
    main()
