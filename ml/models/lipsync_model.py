"""
Lip-Sync Branch — SyncNet-style audio-visual synchronization detector.

Architecture:
  Video stream:   ResNet18 on mouth-crop sequence → video embedding
  Audio stream:   1D CNN on mel-spectrogram → audio embedding
  Sync head:      contrastive / binary cross-entropy on (audio, video) pairs

A high lipsync_score means the mouth video and audio are OUT OF SYNC
which is a strong deepfake signal.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torchvision.models as tvm


class AudioEncoder(nn.Module):
    """1D CNN encoder for mel-spectrogram audio segments."""

    def __init__(self, embedding_dim: int = 512):
        super().__init__()
        self.net = nn.Sequential(
            # Input: (B, 1, n_mels=80, T_audio)
            nn.Conv2d(1, 32, kernel_size=(3, 3), padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 2)),

            nn.Conv2d(32, 64, kernel_size=(3, 3), padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 2)),

            nn.Conv2d(64, 128, kernel_size=(3, 3), padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((4, 4)),
        )
        self.proj = nn.Linear(128 * 4 * 4, embedding_dim)
        self.norm = nn.LayerNorm(embedding_dim)

    def forward(self, mel: torch.Tensor) -> torch.Tensor:
        """
        Args:
            mel: (B, 1, n_mels, T) mel spectrogram

        Returns:
            (B, embedding_dim)
        """
        x = self.net(mel)
        x = x.flatten(1)
        return self.norm(self.proj(x))


class VideoMouthEncoder(nn.Module):
    """ResNet18-based encoder for mouth-region crop sequences."""

    def __init__(self, embedding_dim: int = 512):
        super().__init__()
        enc = tvm.resnet18(weights=tvm.ResNet18_Weights.DEFAULT)
        in_feats = enc.fc.in_features
        enc.fc = nn.Identity()
        self.backbone = enc
        self.temporal_pool = nn.AdaptiveAvgPool1d(1)
        self.proj = nn.Linear(in_feats, embedding_dim)
        self.norm = nn.LayerNorm(embedding_dim)

    def forward(self, mouth_seq: torch.Tensor) -> torch.Tensor:
        """
        Args:
            mouth_seq: (B, T, C, H, W) mouth crops

        Returns:
            (B, embedding_dim)
        """
        B, T, C, H, W = mouth_seq.shape
        flat = mouth_seq.view(B * T, C, H, W)
        feats = self.backbone(flat)                # (B*T, in_feats)
        feats = feats.view(B, T, -1)              # (B, T, in_feats)
        feats = self.temporal_pool(feats.permute(0, 2, 1)).squeeze(-1)  # (B, in_feats)
        return self.norm(self.proj(feats))


class LipSyncModel(nn.Module):
    """
    Full lip-sync detection model.

    Forward returns:
        sync_score: (B,)  0 = in-sync (authentic), 1 = out-of-sync (fake)
        audio_emb:  (B, D)
        video_emb:  (B, D)
    """

    def __init__(self, embedding_dim: int = 512):
        super().__init__()
        self.audio_encoder = AudioEncoder(embedding_dim)
        self.video_encoder = VideoMouthEncoder(embedding_dim)
        self.embedding_dim = embedding_dim

        # Binary sync classifier
        self.sync_head = nn.Sequential(
            nn.Linear(embedding_dim * 2, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, 1),
        )

    def forward(
        self,
        mel: torch.Tensor,
        mouth_seq: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        audio_emb = self.audio_encoder(mel)
        video_emb = self.video_encoder(mouth_seq)

        # Concatenate and classify
        combined = torch.cat([audio_emb, video_emb], dim=-1)
        logit = self.sync_head(combined)

        return {
            "logit": logit,
            "audio_embedding": audio_emb,
            "video_embedding": video_emb,
        }

    def compute_cosine_distance(
        self, audio_emb: torch.Tensor, video_emb: torch.Tensor
    ) -> torch.Tensor:
        """Cosine distance (0=identical, 1=orthogonal, >1 can occur)."""
        audio_n = nn.functional.normalize(audio_emb, dim=-1)
        video_n = nn.functional.normalize(video_emb, dim=-1)
        cos_sim = (audio_n * video_n).sum(dim=-1)
        return (1.0 - cos_sim) / 2.0  # map to [0, 1]
