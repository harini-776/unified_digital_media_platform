"""
Probability Calibration Module.

Implements:
  1. Temperature Scaling (post-hoc, single parameter)
  2. Isotonic Regression (non-parametric)

Also computes ECE (Expected Calibration Error) for evaluation.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from typing import Optional


class TemperatureScaler(nn.Module):
    """
    Post-hoc calibration via temperature scaling.

    Finds optimal T* that minimizes NLL on validation set.
    Applied as: p_calibrated = sigmoid(logit / T*)
    """

    def __init__(self):
        super().__init__()
        self.temperature = nn.Parameter(torch.ones(1))

    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(logits / self.temperature.clamp(min=0.1))

    def fit(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor,
        lr: float = 0.01,
        max_iter: int = 50,
    ) -> float:
        """
        Optimize temperature on validation logits.

        Returns: optimal temperature value
        """
        optimizer = optim.LBFGS([self.temperature], lr=lr, max_iter=max_iter)
        criterion = nn.BCEWithLogitsLoss()

        def closure():
            optimizer.zero_grad()
            loss = criterion(logits / self.temperature.clamp(min=0.1), labels.float())
            loss.backward()
            return loss

        optimizer.step(closure)
        return float(self.temperature.item())


class IsotonicCalibrator:
    """Isotonic regression calibration (sklearn-based)."""

    def __init__(self):
        self.regressor = None

    def fit(self, probs: np.ndarray, labels: np.ndarray):
        from sklearn.isotonic import IsotonicRegression
        self.regressor = IsotonicRegression(out_of_bounds="clip")
        self.regressor.fit(probs, labels)

    def predict(self, probs: np.ndarray) -> np.ndarray:
        if self.regressor is None:
            return probs
        return self.regressor.predict(probs)

    def save(self, path: str):
        import joblib
        joblib.dump(self.regressor, path)

    def load(self, path: str):
        import joblib
        self.regressor = joblib.load(path)


def compute_ece(
    probs: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 15,
) -> float:
    """
    Expected Calibration Error.

    ECE = sum_b (|B_b|/N) * |acc(B_b) - conf(B_b)|

    Args:
        probs:  (N,) predicted probabilities
        labels: (N,) binary ground truth
        n_bins: number of equal-width bins

    Returns:
        ECE in [0, 1]  (lower = better calibrated)
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    N = len(probs)

    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (probs >= lo) & (probs < hi)
        if mask.sum() == 0:
            continue
        bin_acc = labels[mask].mean()
        bin_conf = probs[mask].mean()
        ece += (mask.sum() / N) * abs(bin_acc - bin_conf)

    return float(ece)


def compute_eer(fpr: np.ndarray, tpr: np.ndarray, thresholds: np.ndarray) -> float:
    """Equal Error Rate: point where FPR = FNR."""
    fnr = 1.0 - tpr
    eer_idx = np.nanargmin(np.abs(fnr - fpr))
    return float((fpr[eer_idx] + fnr[eer_idx]) / 2.0)
