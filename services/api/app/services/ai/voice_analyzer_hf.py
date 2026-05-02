"""
HuggingFace voice deepfake detector backend.

Wraps `MelodyMachine/Deepfake-audio-detection-V2` (Wav2Vec2-based,
Apache-2.0). Selected via env var VOICE_BACKEND=hf.

⚠ Label convention is INVERTED from the face HF model:
    voice  HF: {0: fake, 1: real}   → use prob[:, 0] for fake_score
    face   HF: {0: Realism, 1: Deepfake} → use prob[:, 1] for fake_score
The constant _FAKE_LABEL_ID below is hard-coded from the model's config.json
so a future model swap with a different label mapping fails loudly here.

Returns the same dict shape as analyze_voice() in voice_analyzer.py:
    {"voice_score": float 0-100, "embedding": np.ndarray|None, "details": {...}}

so the rest of the pipeline does not need to know which backend produced it.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import torch

from app.core.config import get_settings

settings = get_settings()

_HF_REPO = "MelodyMachine/Deepfake-audio-detection-V2"
_FAKE_LABEL_ID = 0   # per config.json: {0: fake, 1: real} — verified at probe time
_EMBED_DIM = 768     # Wav2Vec2 hidden size — confirmed via config probe
_TARGET_SR = 16000   # Wav2Vec2 was trained at 16kHz
_MAX_SECS = 10.0     # cap audio to keep CPU inference under ~5s/call

_processor = None
_model = None
_model_loaded = False


def _get_hf_voice_model():
    """Lazy-load the HF voice classifier. Cached. Returns (processor, model) or (None, None)."""
    global _processor, _model, _model_loaded
    if _model_loaded:
        return _processor, _model
    _model_loaded = True
    try:
        from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
        _processor = AutoFeatureExtractor.from_pretrained(_HF_REPO)
        _model = AutoModelForAudioClassification.from_pretrained(_HF_REPO)
        _model.eval().to(settings.model_device)
        # Sanity-check the label mapping at load time so a model swap with
        # a different mapping doesn't silently invert results.
        id2label = getattr(_model.config, "id2label", {})
        # Some configs use string keys, others int — normalize.
        norm = {int(k): str(v).lower() for k, v in id2label.items()}
        if norm.get(_FAKE_LABEL_ID) != "fake":
            print(f"[voice_analyzer_hf] WARNING: expected label {_FAKE_LABEL_ID}='fake', "
                  f"got id2label={id2label}. Voice score may be inverted.")
        print(f"[voice_analyzer_hf] loaded {_HF_REPO}")
        return _processor, _model
    except Exception as exc:
        print(f"[voice_analyzer_hf] load failed: {exc}")
        return None, None


def analyze_voice_hf(audio_path: str | None) -> dict:
    """
    HF-backed voice deepfake analysis.

    Pipeline:
      1. Load audio at 16kHz (Wav2Vec2 native rate); cap at _MAX_SECS for CPU sanity
      2. Feature-extract → forward through Wav2Vec2 classifier with hidden states
      3. Softmax → P(fake) from class 0
      4. Embedding = mean-pooled last hidden state (768D)

    Falls back to a 50.0 neutral score with no embedding when:
      - audio_path is None
      - HF model failed to load
      - audio too short (< 1 sec)
      - librosa load fails
    """
    if audio_path is None:
        return {"voice_score": 50.0, "embedding": None,
                "details": {"note": "No audio", "method": "hf"}}

    processor, model = _get_hf_voice_model()
    if model is None:
        return {"voice_score": 50.0, "embedding": None,
                "details": {"note": "HF model load failed", "method": "hf"}}

    try:
        import librosa
        waveform, sr = librosa.load(audio_path, sr=_TARGET_SR, mono=True)
    except Exception as exc:
        return {"voice_score": 50.0, "embedding": None,
                "details": {"note": f"Audio load failed: {exc}", "method": "hf"}}

    if len(waveform) < _TARGET_SR:
        return {"voice_score": 50.0, "embedding": None,
                "details": {"note": "Audio too short (<1s)", "method": "hf"}}

    # Cap duration to keep CPU inference bounded
    max_samples = int(_MAX_SECS * _TARGET_SR)
    if len(waveform) > max_samples:
        waveform = waveform[:max_samples]

    duration_s = len(waveform) / _TARGET_SR
    device = torch.device(settings.model_device)
    inputs = processor(waveform, sampling_rate=_TARGET_SR, return_tensors="pt").to(device)

    with torch.no_grad():
        out = model(**inputs, output_hidden_states=True)
        # Logits: (1, 2). Softmax for prob; column _FAKE_LABEL_ID = fake.
        probs = torch.softmax(out.logits, dim=-1)
        fake_prob = float(probs[0, _FAKE_LABEL_ID].item())
        # Last hidden state: (1, T, 768). Mean-pool over time → (768,).
        last_hidden = out.hidden_states[-1].squeeze(0)   # (T, 768)
        emb = last_hidden.mean(dim=0).cpu().numpy()       # (768,)

    assert emb.shape == (_EMBED_DIM,), f"unexpected emb shape {emb.shape}"

    return {
        "voice_score": round(fake_prob * 100, 2),
        "embedding": emb,
        "details": {
            "method": "hf_wav2vec2_deepfake_audio_v2",
            "model": _HF_REPO,
            "audio_duration_s": round(duration_s, 2),
            "fake_probability": round(fake_prob * 100, 2),
        },
    }
