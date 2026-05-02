"""
Loss functions for deepfake detection training.

  - FocalLoss: down-weights easy negatives, focuses on hard examples
  - LabelSmoothingBCE: prevents overconfident predictions
  - ContrastiveLoss: for sync/metric learning (lipsync branch)
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    """
    Binary Focal Loss.

    FL(p) = -alpha * (1 - p)^gamma * log(p)

    gamma=2 focuses training on hard, misclassified examples.
    """

    def __init__(self, gamma: float = 2.0, alpha: float = 0.25, label_smoothing: float = 0.0):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha
        self.label_smoothing = label_smoothing

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Args:
            logits:  (B, 1) or (B,)
            targets: (B,) binary labels
        """
        logits = logits.view(-1)
        targets = targets.view(-1).float()

        if self.label_smoothing > 0:
            targets = targets * (1 - self.label_smoothing) + 0.5 * self.label_smoothing

        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        probs = torch.sigmoid(logits)
        p_t = probs * targets + (1 - probs) * (1 - targets)
        focal_weight = (1 - p_t) ** self.gamma
        alpha_weight = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        loss = alpha_weight * focal_weight * bce

        return loss.mean()


class LabelSmoothingBCE(nn.Module):
    """BCE with label smoothing."""

    def __init__(self, smoothing: float = 0.1):
        super().__init__()
        self.smoothing = smoothing

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        logits = logits.view(-1)
        targets = targets.view(-1).float()
        targets_smooth = targets * (1 - self.smoothing) + 0.5 * self.smoothing
        return F.binary_cross_entropy_with_logits(logits, targets_smooth)


class ContrastiveLoss(nn.Module):
    """
    Contrastive loss for lip-sync metric learning.

    Pulls in-sync (authentic) pairs together, pushes out-of-sync (fake) apart.
    """

    def __init__(self, margin: float = 1.0):
        super().__init__()
        self.margin = margin

    def forward(
        self,
        audio_emb: torch.Tensor,
        video_emb: torch.Tensor,
        labels: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            audio_emb: (B, D)
            video_emb: (B, D)
            labels:    (B,) 0=in-sync (real), 1=out-of-sync (fake)
        """
        dist = F.pairwise_distance(audio_emb, video_emb)
        pos_loss = (1 - labels.float()) * dist.pow(2)
        neg_loss = labels.float() * F.relu(self.margin - dist).pow(2)
        return (pos_loss + neg_loss).mean()
