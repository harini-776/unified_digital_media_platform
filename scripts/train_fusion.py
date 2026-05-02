"""
Train Fusion Model.

Two source modes:
  --source manifest       : original — expects expert_scores_<split>.npy from
                            scripts/extract_expert_scores.py (full dataset path)
  --source uploads-cache  : reads data/cache/fusion/*.npz produced by
                            scripts/extract_expert_outputs.py (HF backend path)

For uploads-cache, also pass --mode full (default) to train the embedding-aware
FusionModel, or --mode score-only for the simple 5→1 ScoreOnlyFusion.

The mode=full path expects embedding dims to match data/cache/dims.json.

Usage:
    python scripts/train_fusion.py --source manifest --manifest data/manifest.json
    python scripts/train_fusion.py --source uploads-cache --mode full
"""
from __future__ import annotations
import argparse, glob, shutil, sys, os, time
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

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
UPLOADS_CACHE_DIR = os.path.join(REPO_ROOT, "data/cache/fusion")
DIMS_FILE = os.path.join(REPO_ROOT, "data/cache/dims.json")


def load_expert_predictions(manifest_path, split, scores_cache):
    cache_file = os.path.join(scores_cache, f"expert_scores_{split}.npy")
    if not os.path.exists(cache_file):
        raise FileNotFoundError(
            f"Expert scores cache not found: {cache_file}\n"
            "Run: python scripts/extract_expert_scores.py --manifest data/manifest.json"
        )
    data = np.load(cache_file)
    return data[:, :5], data[:, 5].astype(int)


def load_uploads_cache(cache_dir: str = UPLOADS_CACHE_DIR) -> dict[str, list[dict]]:
    """
    Read every fusion_*.npz produced by extract_expert_outputs.py and bucket
    by split. Each item carries scores, embeddings, label, is_synth.
    """
    if not os.path.isdir(cache_dir):
        raise FileNotFoundError(
            f"Uploads cache not found: {cache_dir}\n"
            "Run: FACE_BACKEND=hf VOICE_BACKEND=hf python scripts/extract_expert_outputs.py --force"
        )
    by_split: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    files = sorted(glob.glob(os.path.join(cache_dir, "fusion_*.npz")))
    if not files:
        raise FileNotFoundError(f"No fusion_*.npz under {cache_dir}")
    for p in files:
        d = np.load(p, allow_pickle=False)
        split = str(d["split"])
        # Validity flags were added in B-4a; older npz files (B-3 era) don't
        # have them. Default to True so legacy caches still work — the
        # assertion that runs later will compute on whatever's actually present.
        by_split.setdefault(split, []).append({
            "scores":      d["scores"].astype(np.float32),       # (5,) in [0,1]
            "face_emb":    d["face_emb"].astype(np.float32),
            "voice_emb":   d["voice_emb"].astype(np.float32),
            "lipsync_emb": d["lipsync_emb"].astype(np.float32),
            "label":       float(d["label"]),
            "is_synth":    bool(d["is_synth"]),
            "face_emb_valid":    bool(d["face_emb_valid"])    if "face_emb_valid"    in d.files else True,
            "voice_emb_valid":   bool(d["voice_emb_valid"])   if "voice_emb_valid"   in d.files else True,
            "lipsync_emb_valid": bool(d["lipsync_emb_valid"]) if "lipsync_emb_valid" in d.files else True,
        })
    for s, items in by_split.items():
        n_pos = sum(1 for it in items if it["label"] == 1.0)
        n_synth = sum(1 for it in items if it["is_synth"])
        print(f"  [{s}] {len(items)} samples ({n_pos} fake = {n_synth} synth + {n_pos-n_synth} real, "
              f"{len(items)-n_pos} real)")
    return by_split


class FusionDataset(Dataset):
    """Score-only dataset (legacy manifest path)."""
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


class UploadsFusionDataset(Dataset):
    """
    Embedding-aware dataset built from extract_expert_outputs.py's per-video npz cache.
    Yields scores (5,) AND embeddings dict {face,voice,lipsync} for FusionModel.forward.
    """
    def __init__(self, items: list[dict], modality_dropout_prob: float = 0.2):
        self.items = items
        self.modality_dropout_prob = modality_dropout_prob

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        it = self.items[idx]
        scores = torch.from_numpy(it["scores"].copy())
        face_emb    = torch.from_numpy(it["face_emb"])
        voice_emb   = torch.from_numpy(it["voice_emb"])
        lipsync_emb = torch.from_numpy(it["lipsync_emb"])

        # Score-side modality dropout (legacy behavior). Embedding-side dropout
        # is handled inside FusionModel.forward(self.training).
        if self.modality_dropout_prob > 0 and torch.rand(1).item() < self.modality_dropout_prob:
            zero_idx = torch.randint(0, 5, (1,)).item()
            scores[zero_idx] = 0.5

        return {
            "scores":      scores,
            "face_emb":    face_emb,
            "voice_emb":   voice_emb,
            "lipsync_emb": lipsync_emb,
            "label":       torch.tensor(it["label"], dtype=torch.float32),
        }


def build_score_dicts(batch_scores, device):
    keys = ["face", "lipsync", "voice", "blink", "headmotion"]
    return {k: batch_scores[:, i:i+1].to(device) for i, k in enumerate(keys)}


def build_emb_dicts(batch, device):
    """For UploadsFusionDataset batches: package face/voice/lipsync embeddings."""
    return {
        "face":    batch["face_emb"].to(device),
        "voice":   batch["voice_emb"].to(device),
        "lipsync": batch["lipsync_emb"].to(device),
    }


def backup_existing_fusion(checkpoint_dir: str):
    """
    Before overwriting weights/fusion/best.pt, copy it to *_scoreonly.pt.bak so
    A-3's loader can fall back if the new FusionModel turns out to be worse.
    Same for temperature.pt → temperature_scoreonly.pt.bak.
    """
    primary = os.path.join(checkpoint_dir, "best.pt")
    primary_temp = os.path.join(checkpoint_dir, "temperature.pt")
    backup = os.path.join(checkpoint_dir, "best_scoreonly.pt.bak")
    backup_temp = os.path.join(checkpoint_dir, "temperature_scoreonly.pt.bak")
    if os.path.exists(primary) and not os.path.exists(backup):
        shutil.copy2(primary, backup)
        print(f"  backed up {primary} → {backup}")
    if os.path.exists(primary_temp) and not os.path.exists(backup_temp):
        shutil.copy2(primary_temp, backup_temp)
        print(f"  backed up {primary_temp} → {backup_temp}")


def _run_one(model, batch, device, mode: str) -> dict:
    """Single forward through either FusionModel(scores+embs) or ScoreOnlyFusion(scores).
    Mode is 'full' or 'score-only'."""
    scores = batch["scores"].to(device)
    if mode == "score-only":
        return model(scores)
    score_dict = build_score_dicts(scores, device)
    if "face_emb" in batch:
        emb_dict = build_emb_dicts(batch, device)
        return model(score_dict, embeddings=emb_dict)
    return model(score_dict)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str, default="manifest",
                        choices=["manifest", "uploads-cache"],
                        help="manifest = legacy expert_scores_<split>.npy; "
                             "uploads-cache = data/cache/fusion/*.npz from extract_expert_outputs.py")
    parser.add_argument("--mode", type=str, default="full", choices=["full", "score-only"],
                        help="full = embedding-aware FusionModel; score-only = ScoreOnlyFusion")
    parser.add_argument("--manifest",     type=str, default=None,
                        help="Required for --source manifest")
    parser.add_argument("--config",       type=str, default="ml/configs/config.yaml")
    parser.add_argument("--scores_cache", type=str, default="data/expert_scores")
    parser.add_argument("--epochs",       type=int, default=None,
                        help="Override config epochs")
    parser.add_argument("--no-backup",    action="store_true",
                        help="Skip backing up existing best.pt before overwriting")
    # Legacy alias — old --score_only kept working for back-compat
    parser.add_argument("--score_only",   action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.score_only:
        args.mode = "score-only"

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    fc = cfg["fusion"]
    set_seed(cfg["seed"])
    device = torch.device(cfg["device"] if torch.cuda.is_available() else "cpu")
    epochs = args.epochs or fc["epochs"]
    print(f"Device: {device}  source={args.source}  mode={args.mode}  epochs={epochs}")

    # ── Backup existing fusion checkpoint before any overwrite ────────────
    if not args.no_backup:
        backup_existing_fusion(fc["checkpoint_dir"])

    # ── Build dataset ─────────────────────────────────────────────────────
    if args.source == "uploads-cache":
        by_split = load_uploads_cache()
        if not by_split.get("train"):
            raise SystemExit("uploads-cache has no train split — re-run extract_expert_outputs.py")
        if not by_split.get("val"):
            print("WARN: no val split — using train for val (overfitting metric, not generalization)")
            by_split["val"] = by_split["train"]

        # B-4a: refuse to train if positive face or voice embeddings are mostly
        # invalid (i.e. the HF analyzer fell back to heuristic / failed to load
        # and returned a zero embedding). Lipsync is intentionally NOT guarded:
        # weights/lipsync/best.pt was never trained, so the lipsync analyzer
        # always falls back to the heuristic which returns embedding=None.
        # The fusion model's lipsync gate sees a zero embedding by deployment
        # design — that's a known limitation documented in JOURNAL_PAPER.md
        # §9.2, not a B-4a regression. The lipsync SCORE is still real signal.
        if args.mode == "full":
            train_pos = [it for it in by_split["train"] if it["label"] == 1.0]
            if train_pos:
                rates = {
                    "face":    sum(1 for it in train_pos if it["face_emb_valid"])    / len(train_pos),
                    "voice":   sum(1 for it in train_pos if it["voice_emb_valid"])   / len(train_pos),
                    "lipsync": sum(1 for it in train_pos if it["lipsync_emb_valid"]) / len(train_pos),
                }
                print(f"  positive embedding-validity rates: "
                      f"face={rates['face']:.0%}  voice={rates['voice']:.0%}  "
                      f"lipsync={rates['lipsync']:.0%} (lipsync expected 0%, no trained weights)")
                # Only face and voice are gated. Lipsync is informational.
                low = [b for b in ("face", "voice") if rates[b] < 0.80]
                if low:
                    raise SystemExit(
                        f"refusing to train --mode full: positive {','.join(low)} embedding-validity "
                        f"below 80%. Re-run extract_expert_outputs.py with FACE_BACKEND=hf "
                        f"VOICE_BACKEND=hf, or train --mode score-only instead."
                    )

        train_ds = UploadsFusionDataset(by_split["train"], fc["modality_dropout_prob"])
        val_ds   = UploadsFusionDataset(by_split["val"], 0.0)
    else:
        if not args.manifest:
            raise SystemExit("--manifest required when --source manifest")
        X_train, y_train = load_expert_predictions(args.manifest, "train", args.scores_cache)
        X_val,   y_val   = load_expert_predictions(args.manifest, "val",   args.scores_cache)
        print(f"Train: {len(X_train)}  Val: {len(X_val)}")
        train_ds = FusionDataset(X_train / 100.0, y_train, fc["modality_dropout_prob"])
        val_ds   = FusionDataset(X_val   / 100.0, y_val,   0.0)

    # On a tiny dataset (<200 samples), num_workers=2 incurs more overhead than
    # it saves; main-thread loading is fine.
    nw = 0 if len(train_ds) < 200 else 2
    train_loader = DataLoader(train_ds, batch_size=fc["batch_size"], shuffle=True,  num_workers=nw)
    val_loader   = DataLoader(val_ds,   batch_size=fc["batch_size"], shuffle=False, num_workers=nw)

    # ── Build model ───────────────────────────────────────────────────────
    if args.mode == "score-only":
        model = ScoreOnlyFusion(hidden_dim=fc["hidden_dim"], dropout=fc["dropout"]).to(device)
    else:
        # For uploads-cache with HF backends, dims live in data/cache/dims.json.
        # For manifest mode (no embeddings), pass 0 to disable embedding gates.
        if args.source == "uploads-cache":
            with open(DIMS_FILE) as f:
                dims = json.load(f)
            face_d, voice_d, lipsync_d = int(dims["face"]), int(dims["voice"]), int(dims["lipsync"])
            print(f"  embedding dims (from dims.json): face={face_d} voice={voice_d} lipsync={lipsync_d}")
        else:
            face_d = voice_d = lipsync_d = 0
        model = FusionModel(
            gate_out_dim=64, hidden_dim=fc["hidden_dim"], dropout=fc["dropout"],
            modality_dropout_prob=fc["modality_dropout_prob"],
            face_emb_dim=face_d, voice_emb_dim=voice_d, lipsync_emb_dim=lipsync_d,
        ).to(device)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  model: {type(model).__name__}  params={n_params/1e6:.2f}M")

    # ── Loss / optimizer ──────────────────────────────────────────────────
    # With heavy class imbalance (e.g. uploads-cache: ~1 fake per ~3 reals after
    # synth audio fakes), pos_weight in BCEWithLogits gives the gradient enough
    # signal. FocalLoss alone struggles on n<200 imbalanced data.
    n_pos = sum(1 for it in (by_split["train"] if args.source == "uploads-cache" else [])
                if it["label"] == 1.0) if args.source == "uploads-cache" else None
    n_neg = (len(by_split["train"]) - n_pos) if n_pos is not None else None
    pos_weight = max(1.0, n_neg / max(n_pos, 1)) if n_pos else 1.0
    if args.source == "uploads-cache":
        print(f"  class balance: pos={n_pos} neg={n_neg} → pos_weight={pos_weight:.2f}")

    criterion = FocalLoss(gamma=fc["focal_loss_gamma"], label_smoothing=fc["label_smoothing"])
    optimizer = AdamW(model.parameters(), lr=fc["lr"], weight_decay=fc["weight_decay"])
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs)
    early_stop = EarlyStopping(patience=7, min_delta=0.01, mode="max")

    os.makedirs(fc["checkpoint_dir"], exist_ok=True)
    best_auc = 0.0

    # ── Training loop ─────────────────────────────────────────────────────
    for epoch in range(epochs):
        model.train()
        train_probs, train_labels = [], []
        for batch in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}", leave=False):
            labels = batch["label"].to(device)
            optimizer.zero_grad()
            out = _run_one(model, batch, device, args.mode)
            loss = criterion(out["logit"].squeeze(-1), labels)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_probs.extend(out["probability"].detach().cpu().tolist())
            train_labels.extend(labels.cpu().tolist())

        model.eval()
        val_probs, val_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                out = _run_one(model, batch, device, args.mode)
                val_probs.extend(out["probability"].cpu().tolist())
                val_labels.extend(batch["label"].tolist())

        train_m = compute_metrics(train_probs, train_labels)
        val_m   = compute_metrics(val_probs, val_labels)
        scheduler.step()
        print(f"Ep{epoch+1:>2} | train auc={train_m['auc_roc']:.4f} f1={train_m['f1']:.4f} | "
              f"val auc={val_m['auc_roc']:.4f} f1={val_m['f1']:.4f}")

        if val_m["auc_roc"] > best_auc:
            best_auc = val_m["auc_roc"]
            save_checkpoint(
                model, optimizer, epoch, best_auc,
                os.path.join(fc["checkpoint_dir"], "best.pt"),
                extra={"mode": args.mode, "source": args.source},
            )
            print(f"  ** New best val AUC: {best_auc:.4f} — checkpoint saved **")

        if early_stop.step(val_m["auc_roc"]):
            print("Early stopping triggered."); break

    # ── Temperature calibration ───────────────────────────────────────────
    # Only meaningful when val has both classes — otherwise NLL is degenerate.
    val_unique = set(val_labels)
    if len(val_unique) >= 2:
        print("\nCalibrating on val set...")
        model.eval()
        all_logits, all_labs = [], []
        with torch.no_grad():
            for batch in val_loader:
                out = _run_one(model, batch, device, args.mode)
                all_logits.append(out["logit"].cpu())
                all_labs.extend(batch["label"].tolist())
        logits_t = torch.cat(all_logits).squeeze(-1)
        labels_t = torch.tensor(all_labs)
        T = TemperatureScaler().fit(logits_t, labels_t)
        print(f"  Optimal temperature: {T:.4f}")
        torch.save({"temperature": T}, os.path.join(fc["checkpoint_dir"], "temperature.pt"))
    else:
        print(f"\nSkipping temperature calibration: val has only one class ({val_unique})")
        # Write a no-op temperature so downstream loaders don't break
        torch.save({"temperature": 1.0}, os.path.join(fc["checkpoint_dir"], "temperature.pt"))

    # ── Preserve trained checkpoint as evidence (B-4a) ────────────────────
    # The verifier's auto-rollback may overwrite weights/fusion/best.pt with the
    # ScoreOnlyFusion baseline if FusionModel regresses. Keep a permanent
    # timestamped copy here so we always have the trained artifact for the
    # thesis, regardless of whether it survived the gate. Mirrors B-2a's
    # weights/face/best_resnet18_uploads_REGRESSED.pt pattern.
    if args.mode == "full":
        import shutil, time as _time
        ts = _time.strftime("%Y%m%d_%H%M%S")
        src = os.path.join(fc["checkpoint_dir"], "best.pt")
        dst = os.path.join(fc["checkpoint_dir"], f"best_full_{ts}.pt")
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  preserved trained checkpoint -> {dst}")
        else:
            print(f"  WARN: no best.pt to preserve at {src}")

    print(f"\nDone. Best val AUC-ROC: {best_auc:.4f}")


if __name__ == "__main__":
    main()
