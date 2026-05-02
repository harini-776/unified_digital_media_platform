"""
Voice Authenticity Branch — Production Inference.

Upgrades from embedding uniformity heuristic to trained VoiceModel
(wav2vec2 + MFCC CNN) classifier.
"""
from __future__ import annotations
import os, sys, numpy as np, torch
import librosa
from app.core.config import get_settings

settings = get_settings()

_WEIGHTS = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "../../../../../weights/voice/best.pt"
))

_voice_model = None
_wav2vec_extractor = None
_model_loaded = False


def _get_voice_model():
    global _voice_model, _wav2vec_extractor, _model_loaded
    if _model_loaded:
        return _voice_model, _wav2vec_extractor
    _model_loaded = True
    if not os.path.exists(_WEIGHTS):
        return None, None
    try:
        root = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../../../"))
        if root not in sys.path:
            sys.path.insert(0, root)
        from ml.models.voice_model import VoiceModel, Wav2Vec2FeatureExtractor
        model = VoiceModel(wav2vec2_dim=768, spectral_n_features=40, embedding_dim=256)
        ckpt = torch.load(_WEIGHTS, map_location="cpu")
        model.load_state_dict(ckpt["model_state"])
        model.eval().to(settings.model_device)
        w2v = Wav2Vec2FeatureExtractor(device=settings.model_device)
        _voice_model = model
        _wav2vec_extractor = w2v
        return model, w2v
    except Exception as exc:
        print(f"[voice] model load failed: {exc}")
        return None, None


def _heuristic_voice(audio_path):
    """
    Improved voice heuristic using multiple spectral features.

    AI-synthesized / cloned voices show:
      - Unnaturally uniform MFCC across time (TTS has no spontaneous variation)
      - Very low spectral flux (flat, machine-generated timbre)
      - Periodic zero-crossing anomalies (quantization artifacts)
      - Over-compressed dynamic range (RMS std is low)

    Real human voices show:
      - Irregular MFCC variation (breathing, accent, natural prosody)
      - Higher spectral flux between phones
      - Natural dynamic range variation
    """
    try:
        waveform, sr = librosa.load(audio_path, sr=16000, mono=True)
    except Exception:
        return {"voice_score": 50.0, "embedding": None, "details": {"note": "Audio load failed"}}

    if len(waveform) < sr // 2:
        return {"voice_score": 50.0, "embedding": None, "details": {"note": "Audio too short"}}

    # ── Feature 1: Spectral flux (frame-to-frame change in spectrum) ──────────
    # AI voices: very low flux (monotone synthesis)
    # Real voices: higher flux due to natural coarticulation
    hop = 512
    stft = np.abs(librosa.stft(waveform, hop_length=hop))
    flux = np.mean(np.diff(stft, axis=1) ** 2)
    # Normalize: real voices typically flux > 0.5; TTS < 0.15
    flux_score = float(np.clip((0.5 - flux) / 0.5 * 60, 0, 60))

    # ── Feature 2: MFCC delta variance ────────────────────────────────────────
    # Real speech: MFCC deltas vary a lot (articulation changes)
    # TTS: very smooth deltas (synthesized from static phoneme model)
    mfcc = librosa.feature.mfcc(y=waveform, sr=sr, n_mfcc=40)
    delta_mfcc = librosa.feature.delta(mfcc)
    delta_var = float(np.mean(np.var(delta_mfcc, axis=1)))
    # High delta_var → real; low → suspicious
    delta_score = float(np.clip((3.0 - delta_var) / 3.0 * 50, 0, 50))

    # ── Feature 3: Pitch regularity via ZCR ───────────────────────────────────
    zcr = librosa.feature.zero_crossing_rate(waveform, hop_length=hop)[0]
    zcr_cv = float(np.std(zcr) / (np.mean(zcr) + 1e-6))
    # Real speech has irregular ZCR (pauses, bursts); TTS is very regular
    zcr_score = float(np.clip((0.8 - zcr_cv) / 0.8 * 40, 0, 40))

    # ── Feature 4: Dynamic range (RMS std) ───────────────────────────────────
    rms = librosa.feature.rms(y=waveform, hop_length=hop)[0]
    rms_cv = float(np.std(rms) / (np.mean(rms) + 1e-6))
    # Real speech: high RMS variation (pauses, emphasis); TTS: flat
    rms_score = float(np.clip((0.6 - rms_cv) / 0.6 * 30, 0, 30))

    # ── Feature 5: Multi-segment MFCC uniformity (original signal) ───────────
    seg_len = sr * 3
    segments = [waveform[i:i+seg_len] for i in range(0, max(1, len(waveform)-seg_len+1), seg_len)]
    sim_score = 0.0
    avg_sim = None
    if len(segments) >= 2:
        feats = [librosa.feature.mfcc(y=s, sr=sr, n_mfcc=20).mean(axis=1) for s in segments[:8]]
        embs = np.array(feats)
        sims = [np.dot(embs[i], embs[j]) /
                (np.linalg.norm(embs[i]) * np.linalg.norm(embs[j]) + 1e-8)
                for i in range(len(embs)) for j in range(i+1, len(embs))]
        avg_sim = float(np.mean(sims))
        # Very high uniformity → TTS/cloned
        if avg_sim > 0.992:
            sim_score = 70.0
        elif avg_sim > 0.985:
            sim_score = 50.0
        elif avg_sim > 0.97:
            sim_score = 30.0

    # ── Combine all signals ───────────────────────────────────────────────────
    # Weight sim_score heavily when available (most reliable single signal)
    if avg_sim is not None:
        combined = 0.35 * sim_score + 0.25 * flux_score + 0.20 * delta_score + 0.10 * zcr_score + 0.10 * rms_score
    else:
        combined = 0.35 * flux_score + 0.30 * delta_score + 0.20 * zcr_score + 0.15 * rms_score

    score = round(float(np.clip(combined, 0, 100)), 2)
    mean_emb = mfcc.mean(axis=1)

    return {
        "voice_score": score,
        "embedding": mean_emb,
        "details": {
            "method": "heuristic_spectral",
            "flux_score": round(flux_score, 2),
            "delta_var_score": round(delta_score, 2),
            "zcr_score": round(zcr_score, 2),
            "rms_score": round(rms_score, 2),
            "sim_score": round(sim_score, 2),
            "spectral_flux": round(float(flux), 5),
            "mfcc_delta_var": round(delta_var, 4),
            "avg_mfcc_sim": round(avg_sim, 4) if avg_sim is not None else None,
        }
    }


def analyze_voice(audio_path: str | None) -> dict:
    """
    Analyze audio for voice cloning / synthesis artifacts.
    Returns voice_score (0=authentic, 100=synthetic), embedding, details.
    """
    if audio_path is None:
        return {"voice_score":50.0,"embedding":None,"details":{"note":"No audio"}}

    model, w2v = _get_voice_model()
    if model is None:
        return _heuristic_voice(audio_path)

    try:
        waveform, sr = librosa.load(audio_path, sr=16000, mono=True)
    except Exception:
        return {"voice_score":50.0,"embedding":None,"details":{"note":"Audio load failed"}}

    if len(waveform) < sr:
        return {"voice_score":50.0,"embedding":None,"details":{"note":"Audio too short"}}

    seg_len = int(3.0*sr)
    if len(waveform) >= seg_len:
        segment = waveform[:seg_len]
    else:
        segment = np.pad(waveform, (0, seg_len-len(waveform)))

    # Wav2vec2 embedding
    w2v_emb = w2v.encode(segment, sr).unsqueeze(0)  # (1, 768)

    # MFCC
    mfcc = librosa.feature.mfcc(y=segment, sr=sr, n_mfcc=40)
    if mfcc.shape[1] >= 128:
        mfcc = mfcc[:,:128]
    else:
        mfcc = np.pad(mfcc, ((0,0),(0,128-mfcc.shape[1])))
    mfcc_t = torch.from_numpy(mfcc.astype(np.float32)).unsqueeze(0)  # (1, 40, 128)

    device = torch.device(settings.model_device)
    model.eval()
    with torch.no_grad():
        out = model(w2v_emb.to(device), mfcc_t.to(device))
        prob = torch.sigmoid(out["logit"]).item()

    voice_score = round(prob*100, 2)
    return {
        "voice_score": voice_score,
        "embedding": out["embedding"].cpu().numpy()[0],
        "details": {
            "method":"ml_wav2vec2_mfcc",
            "fake_probability": voice_score,
            "audio_duration_s": round(len(waveform)/sr, 2),
        }
    }
