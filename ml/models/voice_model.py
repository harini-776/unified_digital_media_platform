"""
Voice Authenticity Branch.

Uses wav2vec2 (or ECAPA) frozen backbone for embeddings, then a small
classifier on top of embedding + spectral features (MFCC, spectral contrast).

voice_score (0-1):  0 = authentic, 1 = synthesized/cloned.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import numpy as np


class SpectralFeatureExtractor(nn.Module):
    """
    Lightweight CNN on MFCC+spectral features.
    Input:  (B, n_features, T_frames)  e.g., (B, 40, T)
    Output: (B, out_dim)
    """

    def __init__(self, n_features: int = 40, out_dim: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(n_features, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.Conv1d(64, 128, kernel_size=5, padding=2),
            nn.BatchNorm1d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool1d(1),
        )
        self.proj = nn.Linear(128, out_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.proj(self.net(x).squeeze(-1))


class VoiceModel(nn.Module):
    """
    Voice authenticity classifier.

    Input:
        wav2vec2_emb:     (B, wav2vec2_dim)   - pre-extracted embedding
        spectral_feats:   (B, n_mfcc, T)      - MFCC features

    Output:
        logit:     (B, 1)
        embedding: (B, D)
    """

    WAV2VEC2_DIM = 768  # wav2vec2-base hidden size

    def __init__(
        self,
        wav2vec2_dim: int = 768,
        spectral_n_features: int = 40,
        embedding_dim: int = 256,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.embedding_dim = embedding_dim

        # Project wav2vec2 embedding
        self.wav2vec_proj = nn.Sequential(
            nn.Linear(wav2vec2_dim, embedding_dim),
            nn.LayerNorm(embedding_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
        )

        # Spectral CNN branch
        self.spectral_enc = SpectralFeatureExtractor(spectral_n_features, embedding_dim // 2)

        # Fusion + classification
        fused_dim = embedding_dim + embedding_dim // 2
        self.head = nn.Sequential(
            nn.Linear(fused_dim, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(128, 1),
        )
        self.fused_proj = nn.Linear(fused_dim, embedding_dim)

    def forward(
        self,
        wav2vec2_emb: torch.Tensor,
        spectral_feats: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        w2v = self.wav2vec_proj(wav2vec2_emb)
        spec = self.spectral_enc(spectral_feats)
        fused = torch.cat([w2v, spec], dim=-1)

        logit = self.head(fused)
        embedding = self.fused_proj(fused)

        return {"logit": logit, "embedding": embedding}


class Wav2Vec2FeatureExtractor:
    """
    Wrapper to extract wav2vec2 embeddings from raw audio.
    The backbone is frozen; only the classifier trains.
    """

    def __init__(self, model_name: str = "facebook/wav2vec2-base", device: str = "cpu"):
        from transformers import Wav2Vec2Model, Wav2Vec2Processor
        self.processor = Wav2Vec2Processor.from_pretrained(model_name)
        self.model = Wav2Vec2Model.from_pretrained(model_name)
        self.model.eval()
        for p in self.model.parameters():
            p.requires_grad = False
        self.device = device
        self.model.to(device)

    @torch.no_grad()
    def encode(self, waveform: np.ndarray, sr: int = 16000) -> torch.Tensor:
        """
        Args:
            waveform: 1D numpy array, 16kHz mono
            sr: sample rate

        Returns:
            (wav2vec2_dim,) mean-pooled embedding
        """
        inputs = self.processor(
            waveform, sampling_rate=sr, return_tensors="pt", padding=True
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        out = self.model(**inputs)
        return out.last_hidden_state.mean(dim=1).squeeze(0).cpu()
