"""
Head Motion Physics Branch.

Uses face landmark / pose estimation to compute yaw/pitch/roll time-series.
Extracts motion physics features (smoothness, jerk, acceleration) and
trains an XGBoost / MLP classifier.

Deepfakes often have:
  - Unnaturally smooth or frozen head motion
  - Inconsistent motion relative to scene background
  - Abrupt pose jumps (GAN artifacts)
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Optional


FEATURE_DIM = 18


@dataclass
class HeadMotionFeatures:
    """Feature vector from yaw/pitch/roll time-series."""
    # Yaw stats
    yaw_mean: float
    yaw_std: float
    yaw_range: float
    # Pitch stats
    pitch_mean: float
    pitch_std: float
    pitch_range: float
    # Roll stats
    roll_mean: float
    roll_std: float
    roll_range: float
    # Motion dynamics
    velocity_mean: float    # mean absolute angular velocity
    velocity_std: float
    jerk_mean: float        # mean absolute jerk (d^3/dt^3)
    acceleration_std: float
    smoothness_score: float # ratio of low-freq to total power
    # Optical flow (if available)
    flow_consistency: float # correlation between pose motion and optical flow
    # Anomaly flags (as float for ML)
    has_frozen_segment: float  # fraction of time with near-zero motion
    has_jump: float            # fraction of frames with large pose jump
    pose_velocity_corr: float  # correlation between yaw and pitch velocity

    def to_array(self) -> np.ndarray:
        return np.array([
            self.yaw_mean, self.yaw_std, self.yaw_range,
            self.pitch_mean, self.pitch_std, self.pitch_range,
            self.roll_mean, self.roll_std, self.roll_range,
            self.velocity_mean, self.velocity_std,
            self.jerk_mean, self.acceleration_std,
            self.smoothness_score,
            self.flow_consistency,
            self.has_frozen_segment,
            self.has_jump,
            self.pose_velocity_corr,
        ], dtype=np.float32)


def extract_headmotion_features(
    yaw: np.ndarray,
    pitch: np.ndarray,
    roll: np.ndarray,
    fps: float = 10.0,
    optical_flow_mag: Optional[np.ndarray] = None,
) -> HeadMotionFeatures:
    """
    Extract physics features from head pose time-series.

    Args:
        yaw:   (T,) yaw angles in degrees
        pitch: (T,) pitch angles in degrees
        roll:  (T,) roll angles in degrees
        fps:   frame rate of the sequence
        optical_flow_mag: (T,) magnitude of optical flow in face region
    """
    T = len(yaw)

    # ── First/second/third derivatives ──────────────────────────
    dt = 1.0 / fps
    dyaw   = np.gradient(yaw, dt)
    dpitch = np.gradient(pitch, dt)
    droll  = np.gradient(roll, dt)

    ddyaw  = np.gradient(dyaw, dt)    # acceleration
    dddyaw = np.gradient(ddyaw, dt)   # jerk

    # Combined angular velocity magnitude
    vel_mag = np.sqrt(dyaw**2 + dpitch**2 + droll**2)
    acc = np.sqrt(np.gradient(dyaw, dt)**2 + np.gradient(dpitch, dt)**2 + np.gradient(droll, dt)**2)
    jerk = np.abs(np.gradient(acc, dt))

    # ── Smoothness via FFT ───────────────────────────────────────
    if T >= 8:
        fft_yaw = np.abs(np.fft.rfft(yaw))
        freqs = np.fft.rfftfreq(T, d=1.0/fps)
        cutoff_idx = np.searchsorted(freqs, 2.0)   # < 2 Hz = low freq
        low_power = fft_yaw[:cutoff_idx].sum()
        total_power = fft_yaw.sum() + 1e-6
        smoothness = float(low_power / total_power)
    else:
        smoothness = 0.5

    # ── Frozen segment detection ─────────────────────────────────
    frozen_thresh = 0.5  # degrees/s
    frozen_frac = float((vel_mag < frozen_thresh).mean())

    # ── Jump detection ───────────────────────────────────────────
    jump_thresh = 15.0  # degrees/frame
    frame_deltas = np.abs(np.diff(yaw)) + np.abs(np.diff(pitch)) + np.abs(np.diff(roll))
    jump_frac = float((frame_deltas > jump_thresh).mean()) if len(frame_deltas) > 0 else 0.0

    # ── Cross-modal consistency ──────────────────────────────────
    if optical_flow_mag is not None and len(optical_flow_mag) >= T:
        flow = optical_flow_mag[:T]
        flow_corr = float(np.corrcoef(vel_mag, flow)[0, 1]) if T > 2 else 0.0
    else:
        flow_corr = 0.5  # neutral when not available

    # ── Yaw-pitch velocity correlation ─────────────────────────
    if T > 2:
        py_corr = float(np.corrcoef(np.abs(dyaw), np.abs(dpitch))[0, 1])
    else:
        py_corr = 0.0

    return HeadMotionFeatures(
        yaw_mean=float(np.mean(yaw)),
        yaw_std=float(np.std(yaw)),
        yaw_range=float(np.max(yaw) - np.min(yaw)),
        pitch_mean=float(np.mean(pitch)),
        pitch_std=float(np.std(pitch)),
        pitch_range=float(np.max(pitch) - np.min(pitch)),
        roll_mean=float(np.mean(roll)),
        roll_std=float(np.std(roll)),
        roll_range=float(np.max(roll) - np.min(roll)),
        velocity_mean=float(np.mean(vel_mag)),
        velocity_std=float(np.std(vel_mag)),
        jerk_mean=float(np.mean(jerk)),
        acceleration_std=float(np.std(acc)),
        smoothness_score=smoothness,
        flow_consistency=flow_corr,
        has_frozen_segment=frozen_frac,
        has_jump=jump_frac,
        pose_velocity_corr=py_corr,
    )


class HeadMotionMLP(nn.Module):
    """MLP alternative to XGBoost."""

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


class HeadMotionClassifier:
    """XGBoost or MLP wrapper for head motion classification."""

    def __init__(self, backend: str = "xgboost"):
        self.backend = backend
        self.model = None

    def fit(self, X: np.ndarray, y: np.ndarray):
        if self.backend == "xgboost":
            from xgboost import XGBClassifier
            self.model = XGBClassifier(
                n_estimators=200,
                max_depth=6,
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
        return self.model.predict_proba(X)

    def save(self, path: str):
        import joblib
        joblib.dump(self.model, path)

    def load(self, path: str):
        import joblib
        self.model = joblib.load(path)
