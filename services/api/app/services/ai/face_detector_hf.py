"""
HuggingFace face deepfake detector backend.

Wraps `prithivMLmods/Deep-Fake-Detector-v2-Model` (ViT-base, Apache-2.0,
labels {0:Realism, 1:Deepfake}) so it can be used as a drop-in replacement for
the in-house FaceTemporalModel. Selected via env var FACE_BACKEND=hf.

Per-frame classification → mean-pool over the clip's per-frame fake
probabilities. Embedding is the mean of per-frame [CLS] hidden states (768D).

Returns the same dict shape as analyze_faces() in face_detector.py:
    {"face_score": float 0-100, "embedding": np.ndarray|None, "details": {...}}

so the rest of the pipeline does not need to know which backend produced it.
"""
from __future__ import annotations

import os
from typing import Optional

import cv2
import numpy as np
import torch
from PIL import Image

from app.core.config import get_settings

settings = get_settings()

_HF_REPO = "prithivMLmods/Deep-Fake-Detector-v2-Model"
_DEEPFAKE_LABEL_ID = 1     # per config.json: {0: Realism, 1: Deepfake}
_EMBED_DIM = 768           # ViT-base hidden size — confirmed via config probe

_processor = None
_model = None
_model_loaded = False


def _get_hf_face_model():
    """Lazy-load the HF face classifier. Cached. Returns (processor, model) or (None, None)."""
    global _processor, _model, _model_loaded
    if _model_loaded:
        return _processor, _model
    _model_loaded = True
    try:
        from transformers import AutoImageProcessor, AutoModelForImageClassification
        _processor = AutoImageProcessor.from_pretrained(_HF_REPO)
        _model = AutoModelForImageClassification.from_pretrained(_HF_REPO)
        _model.eval().to(settings.model_device)
        print(f"[face_detector_hf] loaded {_HF_REPO}")
        return _processor, _model
    except Exception as exc:
        print(f"[face_detector_hf] load failed: {exc}")
        return None, None


def _get_mtcnn():
    """Reuse the same MTCNN config the in-house detector uses."""
    from facenet_pytorch import MTCNN
    return MTCNN(keep_all=True, device=torch.device(settings.model_device),
                 select_largest=False, min_face_size=40)


def _align_crop(img_cv: np.ndarray, box: list[float], size: int = 224) -> Optional[np.ndarray]:
    """Crop the face region with margin and resize. Same logic as face_detector._align_crop."""
    x1, y1, x2, y2 = [int(c) for c in box]
    m = int((y2 - y1) * 0.3)
    x1 = max(0, x1 - m); y1 = max(0, y1 - m)
    x2 = min(img_cv.shape[1], x2 + m); y2 = min(img_cv.shape[0], y2 + m)
    crop = img_cv[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB), (size, size))


def analyze_faces_hf(frame_paths: list[str]) -> dict:
    """
    HF-backed face deepfake analysis.

    Pipeline:
      1. MTCNN-detect faces in each frame, crop to 224×224 with margin
      2. Run ViT classifier per crop → softmax → P(Deepfake)
      3. Also collect per-crop [CLS] hidden state (768D)
      4. Mean-pool over crops → final face_score (P(Deepfake)*100), embedding

    Falls back to a 50.0 neutral score with no embedding when:
      - No frames provided
      - HF model failed to load
      - <4 detectable faces across all frames (signal too weak to trust)
    """
    if not frame_paths:
        return {"face_score": 50.0, "embedding": None,
                "details": {"note": "No frames", "method": "hf"}}

    processor, model = _get_hf_face_model()
    if model is None:
        return {"face_score": 50.0, "embedding": None,
                "details": {"note": "HF model load failed", "method": "hf"}}

    mtcnn = _get_mtcnn()
    device = torch.device(settings.model_device)

    # ── Detect + crop faces ─────────────────────────────────────
    crops: list[np.ndarray] = []
    faces_found = 0
    for path in frame_paths:
        img_cv = cv2.imread(path)
        if img_cv is None:
            continue
        img_pil = Image.open(path).convert("RGB")
        boxes, _ = mtcnn.detect(img_pil)
        if boxes is None:
            continue
        faces_found += 1
        # Use the largest detected box per frame
        box = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
        crop = _align_crop(img_cv, box, size=224)
        if crop is not None:
            crops.append(crop)

    if len(crops) < 4:
        return {"face_score": 50.0, "embedding": None,
                "details": {"note": f"Too few faces ({faces_found}/{len(frame_paths)} frames)",
                            "method": "hf"}}

    # ── Classify + collect embeddings ───────────────────────────
    pil_crops = [Image.fromarray(c) for c in crops]
    inputs = processor(images=pil_crops, return_tensors="pt").to(device)

    fake_probs: list[float] = []
    embeddings: list[np.ndarray] = []
    with torch.no_grad():
        out = model(**inputs, output_hidden_states=True)
        # Logits: (N, 2). Softmax for prob; column 1 = Deepfake.
        probs = torch.softmax(out.logits, dim=-1)[:, _DEEPFAKE_LABEL_ID]
        fake_probs = probs.cpu().tolist()
        # Last hidden state: (N, num_tokens, 768). [CLS] is token 0.
        cls = out.hidden_states[-1][:, 0, :]   # (N, 768)
        embeddings = [e.cpu().numpy() for e in cls]

    mean_prob = float(np.mean(fake_probs))
    mean_emb = np.mean(np.stack(embeddings), axis=0)
    assert mean_emb.shape == (_EMBED_DIM,), f"unexpected emb shape {mean_emb.shape}"

    return {
        "face_score": round(mean_prob * 100, 2),
        "embedding": mean_emb,
        "details": {
            "method": "hf_vit_deepfake_detector_v2",
            "model": _HF_REPO,
            "faces_detected_frames": faces_found,
            "total_frames": len(frame_paths),
            "frame_score_std": round(float(np.std(fake_probs)), 4),
        },
    }
