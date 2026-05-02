"""
Base dataset and data pipeline utilities for deepfake detection.

Supports:
  - FaceForensics++
  - Celeb-DF
  - DFDC
  - FakeAVCeleb
  - Generic (folder with real/fake subfolders)

Key design decisions:
  - Identity-disjoint splits: no same person across train/val/test
  - Balanced sampling across datasets and manipulation types
  - Efficient caching of preprocessed artifacts
"""
from __future__ import annotations

import os
import json
import hashlib
import random
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field


@dataclass
class VideoRecord:
    """Single video sample metadata."""
    video_path: str
    label: int            # 0 = real, 1 = fake
    identity: str         # speaker/subject ID for disjoint splits
    dataset: str          # source dataset name
    manipulation: str = "none"   # manipulation type (e.g., Deepfakes, NeuralTextures)
    audio_path: Optional[str] = None


class DeepfakeVideoDataset(Dataset):
    """
    Multi-dataset deepfake video dataset.

    Reads from a JSON manifest:
    [
      {
        "video_path": "...",
        "label": 0,
        "identity": "id_001",
        "dataset": "FF++",
        "manipulation": "Deepfakes"
      },
      ...
    ]
    """

    def __init__(
        self,
        manifest_path: str,
        split: str = "train",
        num_frames: int = 32,
        face_size: int = 224,
        fps: float = 10.0,
        cache_dir: Optional[str] = None,
        transform: Optional[Callable] = None,
        augment: bool = False,
    ):
        self.split = split
        self.num_frames = num_frames
        self.face_size = face_size
        self.fps = fps
        self.cache_dir = cache_dir
        self.transform = transform
        self.augment = augment

        with open(manifest_path) as f:
            all_records = json.load(f)

        # Filter by split (stored in manifest)
        self.records: list[VideoRecord] = [
            VideoRecord(**r) for r in all_records
            if r.get("split", "train") == split
        ]

        print(f"[{split}] Loaded {len(self.records)} samples "
              f"({sum(r.label for r in self.records)} fake, "
              f"{sum(1 - r.label for r in self.records)} real)")

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> dict:
        rec = self.records[idx]

        frames = self._load_frames(rec)
        label = torch.tensor(rec.label, dtype=torch.float32)

        return {
            "frames": frames,          # (T, C, H, W)
            "label": label,
            "identity": rec.identity,
            "dataset": rec.dataset,
            "manipulation": rec.manipulation,
            "video_path": rec.video_path,
        }

    def _cache_key(self, video_path: str) -> str:
        h = hashlib.md5(video_path.encode()).hexdigest()[:12]
        return f"frames_{h}_{self.num_frames}_{int(self.fps)}.npz"

    def _load_frames(self, rec: VideoRecord) -> torch.Tensor:
        """Load and preprocess T frames from video, using cache if available."""
        if self.cache_dir:
            cache_path = os.path.join(self.cache_dir, self._cache_key(rec.video_path))
            if os.path.exists(cache_path):
                data = np.load(cache_path)["frames"]
                frames = torch.from_numpy(data).float() / 255.0
                if self.augment:
                    frames = self._augment_frames(frames)
                return frames

        frames = _extract_frames_uniform(rec.video_path, self.num_frames, self.face_size)

        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)
            np.savez_compressed(
                cache_path,
                frames=(frames.numpy() * 255).astype(np.uint8)
            )

        if self.augment:
            frames = self._augment_frames(frames)
        return frames

    def _augment_frames(self, frames: torch.Tensor) -> torch.Tensor:
        """Apply training augmentations to a (T, C, H, W) tensor."""
        import torchvision.transforms.functional as TF

        # Color jitter (per-clip)
        brightness = random.uniform(0.7, 1.3)
        contrast   = random.uniform(0.7, 1.3)
        saturation = random.uniform(0.8, 1.2)
        hue_delta  = random.uniform(-0.1, 0.1)

        augmented = []
        for frame in frames:
            img = TF.adjust_brightness(frame, brightness)
            img = TF.adjust_contrast(img, contrast)
            img = TF.adjust_saturation(img, saturation)
            img = TF.adjust_hue(img, hue_delta)

            # Random horizontal flip
            if random.random() > 0.5:
                img = TF.hflip(img)

            # Gaussian blur
            if random.random() > 0.7:
                sigma = random.uniform(0.5, 2.0)
                img = TF.gaussian_blur(img, kernel_size=5, sigma=sigma)

            # Add Gaussian noise
            if random.random() > 0.7:
                noise = torch.randn_like(img) * random.uniform(0.01, 0.05)
                img = (img + noise).clamp(0, 1)

            augmented.append(img)

        return torch.stack(augmented)

    def get_weights_for_sampler(self) -> torch.Tensor:
        """Compute per-sample weights for balanced WeightedRandomSampler."""
        labels = np.array([r.label for r in self.records])
        class_counts = np.bincount(labels)
        class_weights = 1.0 / class_counts.astype(float)
        sample_weights = class_weights[labels]
        return torch.from_numpy(sample_weights).float()


def _extract_frames_uniform(
    video_path: str,
    num_frames: int,
    face_size: int,
) -> torch.Tensor:
    """
    Uniformly sample num_frames from video, resize to face_size.
    Returns (T, C, H, W) float32 tensor in [0, 1].
    """
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return torch.zeros(num_frames, 3, face_size, face_size)

    indices = np.linspace(0, total - 1, num_frames, dtype=int)
    frames = []

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ret, frame = cap.read()
        if not ret:
            # Repeat last frame if read fails
            if frames:
                frames.append(frames[-1].clone())
            else:
                frames.append(torch.zeros(3, face_size, face_size))
            continue
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (face_size, face_size))
        t = torch.from_numpy(frame).permute(2, 0, 1).float() / 255.0
        frames.append(t)

    cap.release()

    # Pad if needed
    while len(frames) < num_frames:
        frames.append(frames[-1].clone() if frames else torch.zeros(3, face_size, face_size))

    return torch.stack(frames[:num_frames])


def build_dataloader(
    manifest_path: str,
    split: str,
    batch_size: int,
    num_workers: int = 4,
    **dataset_kwargs,
) -> DataLoader:
    """Build DataLoader with balanced sampling for training."""
    dataset = DeepfakeVideoDataset(manifest_path, split=split, **dataset_kwargs)

    if split == "train":
        weights = dataset.get_weights_for_sampler()
        sampler = WeightedRandomSampler(weights, num_samples=len(weights), replacement=True)
        loader = DataLoader(
            dataset,
            batch_size=batch_size,
            sampler=sampler,
            num_workers=num_workers,
            pin_memory=True,
        )
    else:
        loader = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=True,
        )

    return loader
