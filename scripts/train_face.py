"""
Train Face Artifact + Temporal Branch.

Usage:
    # Manifest mode (real labeled corpus):
    python scripts/train_face.py --source manifest --manifest data/manifest.json

    # Uploads mode (semi-synthetic from services/api/uploads/):
    python scripts/train_face.py --source uploads --epochs 8

Saves best checkpoint to weights/face/best.pt (by val ROC-AUC).
"""
from __future__ import annotations

import argparse
import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from tqdm import tqdm

from ml.models.face_model import FaceTemporalModel
from ml.datasets.base_dataset import build_dataloader
from ml.datasets.uploads_dataset import build_face_dataloader as build_uploads_face_dataloader
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


def _build_loaders(args, cfg, fc):
    """Returns (train_loader, val_loader). Branches on --source."""
    nw = args.num_workers if args.num_workers is not None else cfg["num_workers"]

    if args.source == "uploads":
        # Semi-synthetic CPU-friendly path. Frame cache lives under
        # data/cache/uploads/ so re-runs skip the heavy extraction.
        cache_dir = os.path.join(
            os.path.dirname(__file__), "..", "data", "cache", "uploads"
        )
        kwargs = dict(
            num_frames=args.num_frames or fc["num_frames_train"],
            face_size=cfg["data"]["face_size"],
            cache_dir=os.path.normpath(cache_dir),
        )
        train_loader = build_uploads_face_dataloader(
            "train", batch_size=args.batch_size or fc["batch_size"],
            num_workers=nw, **kwargs
        )
        val_loader = build_uploads_face_dataloader(
            "val", batch_size=args.batch_size or fc["batch_size"],
            num_workers=nw, augment=False, **kwargs
        )
        return train_loader, val_loader

    # Default: manifest mode (existing path)
    if not args.manifest:
        raise SystemExit("--manifest is required when --source=manifest")
    common_kwargs = dict(
        num_frames=fc["num_frames_train"],
        face_size=cfg["data"]["face_size"],
        fps=cfg["data"]["target_fps"],
        cache_dir=cfg["data"]["cache_dir"],
    )
    train_loader = build_dataloader(
        args.manifest, "train", fc["batch_size"],
        augment=True, num_workers=nw, **common_kwargs
    )
    val_loader = build_dataloader(
        args.manifest, "val", fc["batch_size"],
        augment=False, num_workers=nw, **common_kwargs
    )
    return train_loader, val_loader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source",   type=str, default="manifest", choices=["manifest", "uploads"])
    parser.add_argument("--manifest", type=str, default=None,
                        help="Required when --source=manifest")
    parser.add_argument("--config",   type=str, default="ml/configs/config.yaml")
    parser.add_argument("--resume",   type=str, default=None)
    parser.add_argument("--epochs",   type=int, default=None,
                        help="Override config epochs (uploads mode plateaus fast on CPU; default 8)")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--num-frames", type=int, default=None,
                        help="Override num_frames_train (smaller = faster on CPU)")
    parser.add_argument("--num-workers", type=int, default=None,
                        help="Override DataLoader num_workers (0 = main-thread only; safest on CPU with small datasets)")
    parser.add_argument("--backbone", type=str, default=None,
                        help="Override face.backbone (e.g. resnet18 / resnet50 / efficientnet_b4) — smaller backbones cut activation memory")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    fc = cfg["face"]
    set_seed(cfg["seed"])
    device = torch.device(cfg["device"] if torch.cuda.is_available() else "cpu")
    print(f"Device: {device} | source: {args.source}")

    train_loader, val_loader = _build_loaders(args, cfg, fc)

    # Epoch budget — uploads mode defaults to 8 (synthetic-fake training plateaus
    # quickly; long runs overfit the perturbation distribution). Manifest mode
    # keeps the config default of 30 unless explicitly overridden.
    if args.epochs is not None:
        epochs = args.epochs
    elif args.source == "uploads":
        epochs = 8
    else:
        epochs = fc["epochs"]

    backbone = args.backbone or fc["backbone"]
    print(f"Backbone: {backbone}")
    model = FaceTemporalModel(
        backbone=backbone,
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
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs)
    # patience=5 + min_delta=0.02 → don't stop on a single noisy val tick
    # (val set is ~16-32 samples in uploads mode; AUC fluctuates frame-by-frame)
    early_stop = EarlyStopping(patience=5, min_delta=0.02, mode="max")

    start_epoch = 0
    if args.resume:
        start_epoch, _ = load_checkpoint(args.resume, model, optimizer)
        print(f"Resumed from epoch {start_epoch}")

    os.makedirs(fc["checkpoint_dir"], exist_ok=True)
    best_auc = 0.0

    log_dir = os.path.join(os.path.dirname(__file__), "..", "outputs", "training_logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"face_{args.source}_{int(time.time())}.jsonl")
    log_f = open(log_path, "w")
    print(f"Logging per-epoch metrics to {log_path}")

    try:
        for epoch in range(start_epoch, epochs):
            print(f"\nEpoch {epoch+1}/{epochs}")

            train_m = train_epoch(model, train_loader, optimizer, criterion, device)
            val_m   = eval_epoch(model, val_loader, criterion, device)
            scheduler.step()

            print(f"  Train | loss={train_m['loss']:.4f}  auc={train_m['auc_roc']:.4f}  f1={train_m['f1']:.4f}")
            print(f"  Val   | loss={val_m['loss']:.4f}    auc={val_m['auc_roc']:.4f}    f1={val_m['f1']:.4f}")
            log_f.write(json.dumps({"epoch": epoch+1, "train": train_m, "val": val_m}) + "\n")
            log_f.flush()

            if val_m["auc_roc"] > best_auc:
                best_auc = val_m["auc_roc"]
                save_checkpoint(
                    model, optimizer, epoch, best_auc,
                    os.path.join(fc["checkpoint_dir"], "best.pt"),
                    extra={
                        "backbone": backbone,
                        "temporal": fc["temporal"],
                        "embedding_dim": fc["embedding_dim"],
                        "num_heads": fc["temporal_heads"],
                        "num_layers": fc["temporal_layers"],
                        "dropout": fc["dropout"],
                    },
                )
                print(f"  ** New best AUC: {best_auc:.4f} — checkpoint saved **")

            if early_stop.step(val_m["auc_roc"]):
                print("Early stopping triggered.")
                break
    finally:
        log_f.close()

    print(f"\nDone. Best val AUC-ROC: {best_auc:.4f}")
    print(f"Checkpoint: {os.path.join(fc['checkpoint_dir'], 'best.pt')}")
    print(f"Training log: {log_path}")


if __name__ == "__main__":
    main()
