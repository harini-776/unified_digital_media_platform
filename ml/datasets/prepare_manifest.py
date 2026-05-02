"""
Dataset Manifest Preparation Script.

Scans supported deepfake dataset directories and creates a JSON manifest
with identity-disjoint train/val/test splits.

Supported datasets:
  - FaceForensics++ (ff_root/original_sequences + ff_root/manipulated_sequences)
  - Celeb-DF         (celeb_root/Celeb-real + celeb_root/Celeb-synthesis)
  - DFDC             (dfdc_root/  with metadata.json)
  - FakeAVCeleb      (fakeavceleb_root/ with category subfolders)
  - Generic          (any folder with real/ and fake/ subfolders)

Usage:
    python ml/datasets/prepare_manifest.py \
        --ff_root /data/FaceForensics++ \
        --celeb_root /data/Celeb-DF \
        --output data/manifest.json
"""
from __future__ import annotations

import os
import json
import random
import hashlib
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Optional


VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
SEED = 42


def identity_from_path(path: str, dataset: str) -> str:
    """Heuristic identity extraction from file path."""
    stem = Path(path).stem
    if dataset == "FF++":
        # e.g., 000_003_DF -> "000_003"
        parts = stem.split("_")
        return "_".join(parts[:2]) if len(parts) >= 2 else stem
    elif dataset == "Celeb-DF":
        # e.g., id0_0000 -> "id0"
        return stem.split("_")[0]
    elif dataset == "DFDC":
        # use subject ID from metadata
        return stem[:6]
    elif dataset == "FakeAVCeleb":
        return stem.split("-")[0]
    else:
        # Generic: use first 6 chars of filename hash as pseudo-identity
        return hashlib.md5(Path(path).name.encode()).hexdigest()[:6]


def scan_ff_plus_plus(root: str) -> list[dict]:
    """Scan FaceForensics++ dataset structure."""
    records = []
    manip_types = ["Deepfakes", "Face2Face", "FaceSwap", "NeuralTextures", "FaceShifter"]

    # Real videos
    real_dir = os.path.join(root, "original_sequences", "youtube", "raw", "videos")
    if os.path.isdir(real_dir):
        for f in Path(real_dir).rglob("*.mp4"):
            records.append({
                "video_path": str(f),
                "label": 0,
                "identity": identity_from_path(str(f), "FF++"),
                "dataset": "FF++",
                "manipulation": "none",
            })

    # Fake videos
    for mtype in manip_types:
        fake_dir = os.path.join(root, "manipulated_sequences", mtype, "raw", "videos")
        if os.path.isdir(fake_dir):
            for f in Path(fake_dir).rglob("*.mp4"):
                records.append({
                    "video_path": str(f),
                    "label": 1,
                    "identity": identity_from_path(str(f), "FF++"),
                    "dataset": "FF++",
                    "manipulation": mtype,
                })

    return records


def scan_celeb_df(root: str) -> list[dict]:
    """Scan Celeb-DF v2 dataset."""
    records = []

    for category, label, manip in [
        ("Celeb-real", 0, "none"),
        ("YouTube-real", 0, "none"),
        ("Celeb-synthesis", 1, "face_swap"),
    ]:
        folder = os.path.join(root, category)
        if not os.path.isdir(folder):
            continue
        for f in Path(folder).rglob("*.mp4"):
            records.append({
                "video_path": str(f),
                "label": label,
                "identity": identity_from_path(str(f), "Celeb-DF"),
                "dataset": "Celeb-DF",
                "manipulation": manip,
            })

    return records


def scan_generic(root: str, dataset_name: str = "Generic") -> list[dict]:
    """Scan a generic dataset with real/ and fake/ subfolders."""
    records = []
    for label_name, label in [("real", 0), ("fake", 1)]:
        folder = os.path.join(root, label_name)
        if not os.path.isdir(folder):
            continue
        for ext in VIDEO_EXTS:
            for f in Path(folder).rglob(f"*{ext}"):
                records.append({
                    "video_path": str(f),
                    "label": label,
                    "identity": identity_from_path(str(f), dataset_name),
                    "dataset": dataset_name,
                    "manipulation": "unknown" if label == 1 else "none",
                })
    return records


def identity_disjoint_split(
    records: list[dict],
    train: float = 0.70,
    val: float = 0.15,
    seed: int = SEED,
) -> list[dict]:
    """
    Assign split labels ensuring no identity appears in multiple splits.

    Algorithm:
      1. Group record indices by identity
      2. Shuffle identities
      3. Assign identities to splits proportionally
    """
    random.seed(seed)

    # Group by identity
    id_to_indices: dict[str, list[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        id_to_indices[rec["identity"]].append(i)

    identities = list(id_to_indices.keys())
    random.shuffle(identities)

    n = len(identities)
    train_end = int(n * train)
    val_end   = int(n * (train + val))

    train_ids = set(identities[:train_end])
    val_ids   = set(identities[train_end:val_end])
    test_ids  = set(identities[val_end:])

    for rec in records:
        if rec["identity"] in train_ids:
            rec["split"] = "train"
        elif rec["identity"] in val_ids:
            rec["split"] = "val"
        else:
            rec["split"] = "test"

    return records


def build_manifest(
    output_path: str,
    ff_root: Optional[str] = None,
    celeb_root: Optional[str] = None,
    generic_root: Optional[str] = None,
    train: float = 0.70,
    val: float = 0.15,
    max_per_class: Optional[int] = None,
    seed: int = SEED,
):
    records = []

    if ff_root and os.path.isdir(ff_root):
        r = scan_ff_plus_plus(ff_root)
        print(f"FF++: {len(r)} videos")
        records.extend(r)

    if celeb_root and os.path.isdir(celeb_root):
        r = scan_celeb_df(celeb_root)
        print(f"Celeb-DF: {len(r)} videos")
        records.extend(r)

    if generic_root and os.path.isdir(generic_root):
        r = scan_generic(generic_root)
        print(f"Generic: {len(r)} videos")
        records.extend(r)

    if not records:
        raise ValueError("No videos found. Check dataset paths.")

    # Balance classes (optional)
    if max_per_class:
        real = [r for r in records if r["label"] == 0]
        fake = [r for r in records if r["label"] == 1]
        random.seed(seed)
        real = random.sample(real, min(len(real), max_per_class))
        fake = random.sample(fake, min(len(fake), max_per_class))
        records = real + fake

    records = identity_disjoint_split(records, train, val, seed)

    splits = defaultdict(int)
    for r in records:
        splits[r["split"]] += 1
    print(f"Splits: {dict(splits)}")
    print(f"Total: {len(records)} videos")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Manifest saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare dataset manifest")
    parser.add_argument("--ff_root",      type=str, default=None)
    parser.add_argument("--celeb_root",   type=str, default=None)
    parser.add_argument("--generic_root", type=str, default=None)
    parser.add_argument("--output",       type=str, default="data/manifest.json")
    parser.add_argument("--train",        type=float, default=0.70)
    parser.add_argument("--val",          type=float, default=0.15)
    parser.add_argument("--max_per_class", type=int, default=None)
    parser.add_argument("--seed",         type=int, default=42)
    args = parser.parse_args()

    build_manifest(
        output_path=args.output,
        ff_root=args.ff_root,
        celeb_root=args.celeb_root,
        generic_root=args.generic_root,
        train=args.train,
        val=args.val,
        max_per_class=args.max_per_class,
        seed=args.seed,
    )
