"""
Attention-Based Fusion Model.

Takes 5 expert scores + optional intermediate embeddings, fuses them
with a gated attention mechanism, and outputs final fake_probability.

Key features:
  - Modality dropout during training (randomly zeros one expert)
  - Learned per-modality attention weights (interpretable)
  - Temperature scaling integration for calibration
  - Uncertainty estimation via entropy + disagreement
"""
from __future__ import annotations

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class FusionInput:
    """Structured input to the fusion model."""
    face_score: float
    lipsync_score: float
    voice_score: float
    blink_score: float
    headmotion_score: float
    face_embedding: Optional[np.ndarray] = None
    voice_embedding: Optional[np.ndarray] = None
    lipsync_audio_embedding: Optional[np.ndarray] = None


class ModalityGate(nn.Module):
    """
    Learned gate per modality: combines score + embedding into a gated vector.
    Outputs both a gated embedding and an attention weight.
    """

    def __init__(self, score_dim: int = 1, emb_dim: int = 0, out_dim: int = 64):
        super().__init__()
        in_dim = score_dim + emb_dim
        self.gate = nn.Sequential(
            nn.Linear(in_dim, out_dim),
            nn.LayerNorm(out_dim),
            nn.GELU(),
        )
        self.attn_score = nn.Linear(out_dim, 1)

    def forward(self, score: torch.Tensor, emb: Optional[torch.Tensor] = None):
        """
        Args:
            score: (B, 1) normalized score
            emb:   (B, emb_dim) optional embedding

        Returns:
            gated: (B, out_dim)
            attn:  (B, 1) raw attention logit
        """
        if emb is not None:
            x = torch.cat([score, emb], dim=-1)
        else:
            x = score
        gated = self.gate(x)
        attn = self.attn_score(gated)
        return gated, attn


class FusionModel(nn.Module):
    """
    Multi-expert attention fusion model.

    Modalities: face, lipsync, voice, blink, headmotion

    Architecture:
      1. Each modality -> ModalityGate -> (gated_vector, attn_logit)
      2. Softmax over attn_logits -> modality weights
      3. Weighted sum of gated vectors
      4. MLP head -> fake_probability logit
      5. Temperature scaling for calibration

    During training:
      - Modality dropout: randomly zero out one modality
      - This forces the model to be robust to missing signals
    """

    MODALITIES = ["face", "lipsync", "voice", "blink", "headmotion"]

    def __init__(
        self,
        gate_out_dim: int = 64,
        hidden_dim: int = 128,
        dropout: float = 0.3,
        modality_dropout_prob: float = 0.2,
        # Embedding dims (0 = score only)
        face_emb_dim: int = 256,
        voice_emb_dim: int = 256,
        lipsync_emb_dim: int = 512,
    ):
        super().__init__()
        self.modality_dropout_prob = modality_dropout_prob

        # Gates per modality
        self.gates = nn.ModuleDict({
            "face":       ModalityGate(1, face_emb_dim, gate_out_dim),
            "lipsync":    ModalityGate(1, lipsync_emb_dim, gate_out_dim),
            "voice":      ModalityGate(1, voice_emb_dim, gate_out_dim),
            "blink":      ModalityGate(1, 0, gate_out_dim),
            "headmotion": ModalityGate(1, 0, gate_out_dim),
        })

        # Classification head
        self.head = nn.Sequential(
            nn.Linear(gate_out_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

        # Learnable temperature for calibration (initialized to 1.0)
        self.log_temperature = nn.Parameter(torch.zeros(1))

    def forward(
        self,
        scores: dict[str, torch.Tensor],
        embeddings: Optional[dict[str, torch.Tensor]] = None,
        return_weights: bool = False,
    ) -> dict[str, torch.Tensor]:
        """
        Args:
            scores: dict of (B, 1) tensors, values in [0, 1]
                    keys: face, lipsync, voice, blink, headmotion
            embeddings: optional dict of (B, D) tensors
                        keys: face, voice, lipsync
            return_weights: if True, also return modality attention weights

        Returns:
            logit:       (B, 1) raw logit
            probability: (B,)   calibrated probability [0, 1]
            attn_weights: (B, 5) if return_weights=True
        """
        embeddings = embeddings or {}
        B = next(iter(scores.values())).size(0)

        # Modality dropout (training only)
        dropped_modality = None
        if self.training and self.modality_dropout_prob > 0:
            if torch.rand(1).item() < self.modality_dropout_prob:
                dropped_modality = self.MODALITIES[
                    torch.randint(len(self.MODALITIES), (1,)).item()
                ]

        gated_vectors = []
        attn_logits   = []

        for mod in self.MODALITIES:
            score = scores.get(mod, torch.zeros(B, 1, device=next(self.parameters()).device))

            # Apply modality dropout
            if mod == dropped_modality:
                score = torch.zeros_like(score)
                emb = None
            else:
                emb = embeddings.get(mod)

            gated, attn = self.gates[mod](score, emb)
            gated_vectors.append(gated)        # (B, gate_out_dim)
            attn_logits.append(attn)           # (B, 1)

        # Stack attention logits and compute weights
        attn_stack = torch.cat(attn_logits, dim=-1)   # (B, 5)
        attn_weights = F.softmax(attn_stack, dim=-1)  # (B, 5)

        # Weighted sum of gated vectors
        gated_stack = torch.stack(gated_vectors, dim=1)   # (B, 5, gate_out_dim)
        fused = (gated_stack * attn_weights.unsqueeze(-1)).sum(dim=1)  # (B, gate_out_dim)

        # Classification
        logit = self.head(fused)  # (B, 1)

        # Temperature-scaled probability
        temp = self.log_temperature.exp().clamp(min=0.1, max=10.0)
        probability = torch.sigmoid(logit / temp).squeeze(-1)

        result: dict[str, torch.Tensor] = {"logit": logit, "probability": probability}
        if return_weights:
            result["attn_weights"] = attn_weights

        return result

    def compute_uncertainty(
        self,
        scores_list: list[float],
    ) -> tuple[float, str]:
        """
        Compute uncertainty based on:
          1. Entropy of the final probability
          2. Disagreement (std dev) between expert scores

        Returns:
            (entropy_value, uncertainty_label)
        """
        prob = np.mean(scores_list) / 100.0  # rough proxy
        prob = np.clip(prob, 1e-7, 1 - 1e-7)

        # Binary entropy
        entropy = -(prob * math.log2(prob) + (1 - prob) * math.log2(1 - prob))
        entropy_norm = entropy  # already in [0, 1]

        # Disagreement
        disagreement = float(np.std(scores_list))

        if entropy_norm > 0.7 or disagreement > 30.0:
            return entropy_norm, "HIGH"
        elif entropy_norm > 0.3 or disagreement > 15.0:
            return entropy_norm, "MEDIUM"
        else:
            return entropy_norm, "LOW"


class ScoreOnlyFusion(nn.Module):
    """
    Simpler fusion using only the 5 scalar scores (no embeddings).
    Useful when expert embeddings are unavailable.
    """

    def __init__(self, hidden_dim: int = 64, dropout: float = 0.2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(5, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(inplace=True),
            nn.Linear(hidden_dim // 2, 1),
        )
        self.log_temperature = nn.Parameter(torch.zeros(1))

    def forward(self, score_vec: torch.Tensor) -> dict[str, torch.Tensor]:
        logit = self.net(score_vec)
        temp = self.log_temperature.exp().clamp(min=0.1, max=10.0)
        probability = torch.sigmoid(logit / temp).squeeze(-1)
        return {"logit": logit, "probability": probability}
