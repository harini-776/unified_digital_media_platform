"""
Eye Blink Branch.

Uses MediaPipe face mesh to compute Eye Aspect Ratio (EAR) time-series,
then extracts statistical features for an XGBoost / MLP classifier.

Features extracted from EAR sequence:
  - blink_rate_per_min
  - mean/std/min/max EAR
  - blink_duration_mean/std
  - inter_blink_interval_mean/std/cv  (CV = coefficient of variation)
  - ear_irregularity (autocorrelation at lag 1)
  - long_pause_fraction (fraction of time without blink > 5s)
  - micro_blink_count
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Optional


EAR_THRESHOLD = 0.21       # below this = eye closed
MIN_BLINK_FRAMES = 1       # consecutive closed frames = blink
NORMAL_BLINK_RATE = 17.0   # blinks per minute (natural average)
FEATURE_DIM = 14


@dataclass
class BlinkFeatures:
    """Feature vector extracted from EAR time-series."""
    blink_rate_per_min: float
    ear_mean: float
    ear_std: float
    ear_min: float
    ear_max: float
    blink_duration_mean: float
    blink_duration_std: float
    ibi_mean: float           # inter-blink interval (seconds)
    ibi_std: float
    ibi_cv: float             # coefficient of variation
    ear_autocorr_lag1: float
    long_pause_fraction: float
    micro_blink_count: int    # very short blinks (<100ms)
    ear_range: float

    def to_array(self) -> np.ndarray:
        return np.array([
            self.blink_rate_per_min,
            self.ear_mean,
            self.ear_std,
            self.ear_min,
            self.ear_max,
            self.blink_duration_mean,
            self.blink_duration_std,
            self.ibi_mean,
            self.ibi_std,
            self.ibi_cv,
            self.ear_autocorr_lag1,
            self.long_pause_fraction,
            float(self.micro_blink_count),
            self.ear_range,
        ], dtype=np.float32)


def compute_ear(landmarks: np.ndarray, eye_indices: tuple) -> float:
    """
    Compute Eye Aspect Ratio from 6 landmark points.

    EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
    Landmarks ordered: [outer, upper1, upper2, inner, lower2, lower1]
    """
    p = landmarks[list(eye_indices)]
    vert1 = np.linalg.norm(p[1] - p[5])
    vert2 = np.linalg.norm(p[2] - p[4])
    horiz = np.linalg.norm(p[0] - p[3])
    return (vert1 + vert2) / (2.0 * horiz + 1e-6)


# MediaPipe left/right eye landmark indices (from face mesh 468 landmarks)
LEFT_EYE_IDX = (362, 385, 387, 263, 373, 380)
RIGHT_EYE_IDX = (33, 160, 158, 133, 153, 144)


def extract_blink_features(
    ear_sequence: list[float],
    fps: float = 10.0,
    duration_s: Optional[float] = None,
) -> BlinkFeatures:
    """
    Extract blink features from EAR time-series.

    Args:
        ear_sequence: EAR value per frame
        fps: frames per second of the input sequence
        duration_s: video duration (computed from sequence if None)
    """
    arr = np.array(ear_sequence, dtype=np.float32)
    n = len(arr)
    dur = duration_s or (n / fps)

    # ── Blink detection ──────────────────────────────────────────
    closed = arr < EAR_THRESHOLD  # True = eye closed frame

    blinks = []          # list of (start_frame, end_frame)
    in_blink = False
    start = 0
    for i, c in enumerate(closed):
        if c and not in_blink:
            in_blink = True
            start = i
        elif not c and in_blink:
            in_blink = False
            blinks.append((start, i - 1))
    if in_blink:
        blinks.append((start, n - 1))

    blink_count = len(blinks)
    blink_rate = (blink_count / dur) * 60.0 if dur > 0 else 0.0

    blink_durations = [(b[1] - b[0] + 1) / fps for b in blinks]
    dur_mean = float(np.mean(blink_durations)) if blink_durations else 0.0
    dur_std = float(np.std(blink_durations)) if len(blink_durations) > 1 else 0.0

    # Inter-blink intervals
    if len(blinks) >= 2:
        ibi_list = [(blinks[i+1][0] - blinks[i][1]) / fps for i in range(len(blinks)-1)]
        ibi_mean = float(np.mean(ibi_list))
        ibi_std = float(np.std(ibi_list))
        ibi_cv = ibi_std / (ibi_mean + 1e-6)
    else:
        ibi_mean = dur
        ibi_std = 0.0
        ibi_cv = 0.0

    # Autocorrelation at lag 1 (smoothness of EAR signal)
    if n > 2:
        corr = float(np.corrcoef(arr[:-1], arr[1:])[0, 1])
    else:
        corr = 0.0

    # Long pause (>5s without blink)
    long_pause_thresh = 5.0 * fps
    long_pauses = 0
    if len(blinks) >= 2:
        for i in range(len(blinks)-1):
            gap = blinks[i+1][0] - blinks[i][1]
            if gap > long_pause_thresh:
                long_pauses += gap
    long_pause_frac = long_pauses / n if n > 0 else 0.0

    # Micro-blinks (<100ms = <fps*0.1 frames)
    micro_thresh = fps * 0.1
    micro = sum(1 for d in blink_durations if d * fps < micro_thresh)

    return BlinkFeatures(
        blink_rate_per_min=blink_rate,
        ear_mean=float(np.mean(arr)),
        ear_std=float(np.std(arr)),
        ear_min=float(np.min(arr)),
        ear_max=float(np.max(arr)),
        blink_duration_mean=dur_mean,
        blink_duration_std=dur_std,
        ibi_mean=ibi_mean,
        ibi_std=ibi_std,
        ibi_cv=ibi_cv,
        ear_autocorr_lag1=corr,
        long_pause_fraction=long_pause_frac,
        micro_blink_count=micro,
        ear_range=float(np.max(arr) - np.min(arr)),
    )


class BlinkMLP(nn.Module):
    """Small MLP alternative to XGBoost for blink classification."""

    def __init__(self, input_dim: int = FEATURE_DIM, dropout: float = 0.2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        return {"logit": self.net(x)}


class BlinkClassifier:
    """
    Wrapper that supports either XGBoost or MLP backend.
    During inference, instantiate with load_weights().
    """

    def __init__(self, backend: str = "xgboost"):
        self.backend = backend
        self.model = None

    def fit(self, X: np.ndarray, y: np.ndarray):
        if self.backend == "xgboost":
            from xgboost import XGBClassifier
            self.model = XGBClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                use_label_encoder=False,
                eval_metric="logloss",
            )
            self.model.fit(X, y)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Returns (N, 2) probability array."""
        if self.backend == "xgboost":
            return self.model.predict_proba(X)
        raise RuntimeError("Model not initialized")

    def save(self, path: str):
        import joblib
        joblib.dump(self.model, path)

    def load(self, path: str):
        import joblib
        self.model = joblib.load(path)
