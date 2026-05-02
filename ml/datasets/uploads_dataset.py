"""
Upload-mode dataset module — semi-synthetic training from services/api/uploads/.

For Step B of the training plan: trains face/voice/lipsync experts when no
labeled deepfake corpus (FF++, Celeb-DF, DFDC) is available locally.

Strategy:
  - Each upload = one real sample (label=0).
  - For each real, generate one synthetic-fake counterpart (label=1) by
    applying realistic deepfake-style artifacts (compression, blur, color
    shift, noise).
  - A sidecar labels.csv lets the user mark known real-fakes (label=1)
    explicitly — those bypass synthesis and contribute as authentic positives.
  - deepfake_test_video.mp4 at the repo root is reserved for verify_pipeline.py
    and excluded from training to prevent train/test leakage.

Splits are deterministic via md5(filename) → train (70%) / val (15%) / test (15%),
so re-runs are reproducible without a manifest.

This module currently exposes UploadsFaceDataset only (Phase B-2a).
UploadsVoiceDataset and UploadsLipsyncDataset are added in B-2b/B-2c.
"""
from __future__ import annotations

import csv
import hashlib
import os
import random
from dataclasses import dataclass

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler

from ml.datasets.base_dataset import _extract_frames_uniform


# ─────────────────────────── paths ───────────────────────────

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))
UPLOADS_DIR = os.path.join(REPO_ROOT, "services/api/uploads")
LABELS_CSV = os.path.join(UPLOADS_DIR, "labels.csv")
EXCLUDED_FROM_TRAINING = {"deepfake_test_video.mp4"}  # reserved for verify_pipeline.py


# ─────────────────────── sample record ───────────────────────

@dataclass
class UploadSample:
    """One training sample built from an upload."""
    video_path: str
    label: int           # 0 = real, 1 = fake
    fake_seed: int       # deterministic seed for synthesize_fake; 0 = real (no synthesis)
    is_synthetic: bool   # True if fake came from synthesize_fake (vs labels.csv)


# ────────────────── deterministic split ──────────────────────

def _split_for_filename(filename: str, train_pct: float = 0.70, val_pct: float = 0.15) -> str:
    """Deterministic train/val/test bucket based on md5 of filename."""
    h = int(hashlib.md5(filename.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    if h < train_pct:
        return "train"
    if h < train_pct + val_pct:
        return "val"
    return "test"


# ───────────────────── label loader ──────────────────────────

def _load_user_labels() -> dict[str, int]:
    """
    Read services/api/uploads/labels.csv if present.
    Format: filename,label  (label = 0 real, 1 fake)
    Returns {} if no file exists.
    """
    out: dict[str, int] = {}
    if not os.path.exists(LABELS_CSV):
        return out
    with open(LABELS_CSV) as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#") or row[0].lower() == "filename":
                continue
            if len(row) < 2:
                continue
            try:
                out[row[0].strip()] = int(row[1].strip())
            except ValueError:
                continue
    return out


# ─────────────────── synthetic fake generator ────────────────

def synthesize_fake(frames: torch.Tensor, seed: int) -> torch.Tensor:
    """
    Apply deepfake-style artifacts to a clip. Deterministic given seed.

    Effects (loosely calibrated to mimic real deepfake compression pipelines):
      - Heavy JPEG compression (quality ~25, ≈ CRF 38–42)
      - Gaussian blur (σ uniform in [1.0, 2.0])
      - Per-channel color shift (mimics generator color drift)
      - Mild Gaussian noise
      - Occasional dropped frame (replaced with previous)

    Args:
        frames: (T, C, H, W) float in [0, 1]
        seed:   deterministic random seed
    Returns:
        (T, C, H, W) float in [0, 1] — same shape, perturbed
    """
    rng = np.random.default_rng(seed)
    T, C, H, W = frames.shape

    quality = int(rng.integers(20, 30))
    sigma = float(rng.uniform(1.0, 2.0))
    color_shift = rng.uniform(-0.05, 0.05, size=(3,)).astype(np.float32)
    noise_std = float(rng.uniform(0.01, 0.04))
    drop_prob = 0.05

    out = []
    prev = None
    for t in range(T):
        if prev is not None and rng.random() < drop_prob:
            out.append(prev.clone())
            continue

        img = frames[t].numpy()  # (C, H, W) in [0,1]
        img_hwc = (img.transpose(1, 2, 0) * 255.0).clip(0, 255).astype(np.uint8)

        # JPEG round-trip — the dominant deepfake compression artifact
        ok, enc = cv2.imencode(".jpg", cv2.cvtColor(img_hwc, cv2.COLOR_RGB2BGR),
                               [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok:
            dec = cv2.imdecode(enc, cv2.IMREAD_COLOR)
            img_hwc = cv2.cvtColor(dec, cv2.COLOR_BGR2RGB)

        # Gaussian blur — mimics over-smoothed AI-generated skin texture
        k = max(3, int(sigma * 2) | 1)
        img_hwc = cv2.GaussianBlur(img_hwc, (k, k), sigma)

        # Convert back to float [0,1] CHW
        out_t = torch.from_numpy(img_hwc.transpose(2, 0, 1).astype(np.float32) / 255.0)

        # Per-channel color shift (broadcast over H, W)
        out_t = (out_t + torch.from_numpy(color_shift).view(3, 1, 1)).clamp(0, 1)

        # Gaussian noise
        out_t = (out_t + torch.randn_like(out_t) * noise_std).clamp(0, 1)

        out.append(out_t)
        prev = out_t

    return torch.stack(out)


# ───────────────────── sample list builder ───────────────────

def build_sample_list(
    split: str,
    include_synthetic_fakes: bool = True,
) -> list[UploadSample]:
    """
    Walk uploads dir, apply user labels, generate synthetic-fake counterparts.

    For real (label=0) videos, also emits one synthetic-fake derivative
    (same video_path, fake_seed=hash, label=1) — unless include_synthetic_fakes
    is False (e.g. for val/test sets where we want true samples only).

    User-labeled fakes (from labels.csv) are emitted as fakes WITHOUT also
    creating a synthetic copy of them.
    """
    if not os.path.isdir(UPLOADS_DIR):
        raise FileNotFoundError(f"Uploads directory not found: {UPLOADS_DIR}")

    user_labels = _load_user_labels()
    samples: list[UploadSample] = []
    files = sorted(f for f in os.listdir(UPLOADS_DIR) if f.lower().endswith(".mp4"))

    for fname in files:
        if fname in EXCLUDED_FROM_TRAINING:
            continue
        if _split_for_filename(fname) != split:
            continue

        path = os.path.join(UPLOADS_DIR, fname)
        user_label = user_labels.get(fname)

        if user_label == 1:
            # Real fake from sidecar — no synthesis
            samples.append(UploadSample(path, label=1, fake_seed=0, is_synthetic=False))
        else:
            # Real video (default, or explicit user_label=0)
            samples.append(UploadSample(path, label=0, fake_seed=0, is_synthetic=False))
            if include_synthetic_fakes:
                seed = int(hashlib.md5((fname + "_fake").encode()).hexdigest()[:8], 16)
                samples.append(UploadSample(path, label=1, fake_seed=seed, is_synthetic=True))

    return samples


# ─────────────────── face dataset (B-2a) ─────────────────────

class UploadsFaceDataset(Dataset):
    """
    Face-branch dataset built from services/api/uploads/.

    Each item: {"frames": (T,3,face_size,face_size) float in [0,1], "label": float}
    matching the batch shape consumed by scripts/train_face.py.
    """

    def __init__(
        self,
        split: str = "train",
        num_frames: int = 32,
        face_size: int = 224,
        cache_dir: str | None = None,
        augment: bool = False,
        include_synthetic_fakes: bool = True,
    ):
        self.split = split
        self.num_frames = num_frames
        self.face_size = face_size
        self.cache_dir = cache_dir
        self.augment = augment

        self.samples = build_sample_list(split, include_synthetic_fakes=include_synthetic_fakes)

        n_real = sum(1 for s in self.samples if s.label == 0)
        n_fake = sum(1 for s in self.samples if s.label == 1)
        n_synth = sum(1 for s in self.samples if s.is_synthetic)
        n_real_fake = n_fake - n_synth
        print(f"[uploads-face/{split}] {len(self.samples)} samples "
              f"(real={n_real}, fake={n_fake} = {n_synth} synthetic + {n_real_fake} user-labeled)")

    def __len__(self) -> int:
        return len(self.samples)

    def _cache_key(self, sample: UploadSample) -> str:
        base = os.path.basename(sample.video_path)
        h = hashlib.md5(f"{base}_{sample.fake_seed}_{self.num_frames}_{self.face_size}".encode()).hexdigest()[:12]
        return f"face_{h}.npz"

    def _load_or_extract(self, sample: UploadSample) -> torch.Tensor:
        cache_path = None
        if self.cache_dir:
            cache_path = os.path.join(self.cache_dir, self._cache_key(sample))
            # Read with retry: another DataLoader worker may be writing this
            # file right now. Try the read; on EOFError/BadZip (truncated mid-write),
            # delete and re-extract.
            if os.path.exists(cache_path):
                try:
                    arr = np.load(cache_path)["frames"]
                    return torch.from_numpy(arr).float() / 255.0
                except (EOFError, OSError, ValueError) as exc:
                    print(f"[uploads-face] corrupt cache {os.path.basename(cache_path)} "
                          f"({type(exc).__name__}); regenerating")
                    try:
                        os.remove(cache_path)
                    except OSError:
                        pass

        # Extract clean frames
        frames = _extract_frames_uniform(sample.video_path, self.num_frames, self.face_size)
        if sample.is_synthetic:
            frames = synthesize_fake(frames, sample.fake_seed)

        if cache_path:
            os.makedirs(self.cache_dir, exist_ok=True)
            # Atomic write: save to a per-process tmp file ending in .npz
            # (np.savez_compressed otherwise auto-appends .npz, breaking the rename),
            # then rename. POSIX rename is atomic, so concurrent readers see either
            # the old (missing) state or the complete file — never a half-written one.
            tmp_path = f"{cache_path}.tmp.{os.getpid()}.npz"
            try:
                np.savez_compressed(tmp_path, frames=(frames.numpy() * 255).astype(np.uint8))
                os.replace(tmp_path, cache_path)
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise

        return frames

    def _augment(self, frames: torch.Tensor) -> torch.Tensor:
        """Light augmentation: hflip + color jitter. Reuses base_dataset's pattern."""
        import torchvision.transforms.functional as TF

        brightness = random.uniform(0.8, 1.2)
        contrast   = random.uniform(0.8, 1.2)
        do_flip    = random.random() > 0.5

        out = []
        for f in frames:
            x = TF.adjust_brightness(f, brightness)
            x = TF.adjust_contrast(x, contrast)
            if do_flip:
                x = TF.hflip(x)
            out.append(x)
        return torch.stack(out)

    def __getitem__(self, idx: int) -> dict:
        s = self.samples[idx]
        frames = self._load_or_extract(s)
        if self.augment:
            frames = self._augment(frames)
        return {
            "frames": frames,
            "label": torch.tensor(float(s.label), dtype=torch.float32),
            "video_path": s.video_path,
            "is_synthetic": s.is_synthetic,
        }

    def get_weights_for_sampler(self) -> torch.Tensor:
        labels = np.array([s.label for s in self.samples])
        counts = np.bincount(labels, minlength=2).astype(float)
        # Avoid div-by-zero if a class is empty in this split
        counts[counts == 0] = 1.0
        class_w = 1.0 / counts
        return torch.from_numpy(class_w[labels]).float()


def build_face_dataloader(
    split: str,
    batch_size: int,
    num_workers: int = 0,
    augment: bool | None = None,
    include_synthetic_fakes: bool | None = None,
    **dataset_kwargs,
) -> DataLoader:
    """
    DataLoader factory mirroring base_dataset.build_dataloader's API.

    Defaults:
      - augment auto-on for train, off otherwise
      - include_synthetic_fakes auto-on for train, off for val/test
        (val/test should reflect the true real distribution)
    """
    if augment is None:
        augment = split == "train"
    if include_synthetic_fakes is None:
        # Synthesis must be on for all splits — without fake samples in val,
        # AUC is undefined and early-stopping on val AUC becomes a no-op.
        # Seeds are deterministic per filename, so val/test fakes are stable
        # across runs and structurally identical to (but distinct from) train fakes.
        include_synthetic_fakes = True

    ds = UploadsFaceDataset(
        split=split,
        augment=augment,
        include_synthetic_fakes=include_synthetic_fakes,
        **dataset_kwargs,
    )

    if split == "train" and len(ds) > 0:
        weights = ds.get_weights_for_sampler()
        sampler = WeightedRandomSampler(weights, num_samples=len(weights), replacement=True)
        return DataLoader(ds, batch_size=batch_size, sampler=sampler,
                          num_workers=num_workers, pin_memory=False)
    return DataLoader(ds, batch_size=batch_size, shuffle=False,
                      num_workers=num_workers, pin_memory=False)
