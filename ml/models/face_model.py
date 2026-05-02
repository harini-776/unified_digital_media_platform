"""
Face Artifact + Temporal Branch.

Architecture:
  EfficientNet-B4 backbone  →  per-frame spatial embeddings
  Temporal Transformer      →  sequence modeling across T frames
  MLP head                  →  face_score (0–1)

Handles variable-length input via uniform temporal sampling (T=32 frames).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torchvision.models as tvm
from typing import Optional


class TemporalTransformer(nn.Module):
    """Lightweight Transformer over frame sequence embeddings."""

    def __init__(self, embed_dim: int, num_heads: int = 4, num_layers: int = 2, dropout: float = 0.1):
        super().__init__()
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=embed_dim * 2,
            dropout=dropout,
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, T, D) frame embeddings

        Returns:
            (B, D) aggregated sequence representation
        """
        B = x.size(0)
        cls = self.cls_token.expand(B, -1, -1)  # (B, 1, D)
        x = torch.cat([cls, x], dim=1)          # (B, T+1, D)
        out = self.transformer(x)
        return out[:, 0]                          # CLS token → (B, D)


class FaceTemporalModel(nn.Module):
    """
    EfficientNet-B4 + Temporal Transformer for face deepfake detection.

    Input:
        frames: (B, T, C, H, W)  – T=32 aligned face crops, 224×224

    Output:
        logit:     (B, 1)   raw logit
        embedding: (B, D)   temporal embedding for fusion
    """

    EMBED_DIM = 256

    def __init__(
        self,
        backbone: str = "efficientnet_b4",
        temporal: str = "transformer",
        embedding_dim: int = 256,
        num_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.3,
        pretrained: bool = True,
    ):
        super().__init__()
        self.embedding_dim = embedding_dim

        # ── Spatial backbone ────────────────────────────────────────
        if backbone == "efficientnet_b4":
            weights = tvm.EfficientNet_B4_Weights.DEFAULT if pretrained else None
            enc = tvm.efficientnet_b4(weights=weights)
            spatial_dim = enc.classifier[1].in_features
            enc.classifier = nn.Identity()
        elif backbone == "resnet50":
            weights = tvm.ResNet50_Weights.DEFAULT if pretrained else None
            enc = tvm.resnet50(weights=weights)
            spatial_dim = enc.fc.in_features
            enc.fc = nn.Identity()
        else:
            raise ValueError(f"Unknown backbone: {backbone}")

        self.backbone = enc
        self.spatial_proj = nn.Sequential(
            nn.Linear(spatial_dim, embedding_dim),
            nn.LayerNorm(embedding_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
        )

        # ── Temporal module ─────────────────────────────────────────
        self.temporal_module: nn.Module
        if temporal == "transformer":
            self.temporal_module = TemporalTransformer(
                embed_dim=embedding_dim,
                num_heads=num_heads,
                num_layers=num_layers,
                dropout=dropout,
            )
        elif temporal == "lstm":
            self.temporal_module = _LSTMTemporal(embedding_dim, dropout)
        elif temporal == "conv1d":
            self.temporal_module = _Conv1DTemporal(embedding_dim, dropout)
        else:
            raise ValueError(f"Unknown temporal module: {temporal}")

        # ── Classification head ─────────────────────────────────────
        self.head = nn.Sequential(
            nn.Linear(embedding_dim, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
        )

    def forward(
        self,
        frames: torch.Tensor,
        return_embedding: bool = False,
    ) -> dict[str, torch.Tensor]:
        B, T, C, H, W = frames.shape

        # Encode each frame independently
        frames_flat = frames.view(B * T, C, H, W)
        spatial = self.backbone(frames_flat)       # (B*T, spatial_dim)
        spatial = self.spatial_proj(spatial)       # (B*T, D)
        spatial = spatial.view(B, T, -1)           # (B, T, D)

        # Temporal aggregation
        temporal_emb = self.temporal_module(spatial)  # (B, D)

        logit = self.head(temporal_emb)                # (B, 1)

        result = {"logit": logit, "embedding": temporal_emb}
        return result


class _LSTMTemporal(nn.Module):
    def __init__(self, dim: int, dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(dim, dim, num_layers=2, batch_first=True, dropout=dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (h, _) = self.lstm(x)
        return h[-1]


class _Conv1DTemporal(nn.Module):
    def __init__(self, dim: int, dropout: float):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(dim, dim, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.AdaptiveAvgPool1d(1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x.permute(0, 2, 1)).squeeze(-1)
