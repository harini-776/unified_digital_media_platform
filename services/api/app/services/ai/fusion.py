"""
Upgraded Fusion Module — Attention-Based Multi-Expert Fusion.

Replaces static weighted average with:
  - Learned attention fusion (FusionModel) when weights available
  - Temperature-scaled calibrated probabilities
  - Uncertainty quantification (entropy + disagreement)
  - Interpretable per-modality contribution weights
  - Explanation generation
"""
from __future__ import annotations
import json, os, sys, math, numpy as np, torch
from app.models.result import Verdict

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../../../"))
_WEIGHTS = os.path.join(_REPO_ROOT, "weights/fusion/best.pt")
_TEMP_FILE = os.path.join(_REPO_ROOT, "weights/fusion/temperature.pt")
_BACKUP_WEIGHTS = os.path.join(_REPO_ROOT, "weights/fusion/best_scoreonly.pt.bak")
_BACKUP_TEMP = os.path.join(_REPO_ROOT, "weights/fusion/temperature_scoreonly.pt.bak")
_DIMS_FILE = os.path.join(_REPO_ROOT, "data/cache/dims.json")

_fusion_model = None
_temperature = 1.0
_model_loaded = False
_LOADED_MODEL_KIND: str | None = None  # "full" | "score_only" | None


def _read_dims() -> dict[str, int]:
    if os.path.exists(_DIMS_FILE):
        try:
            with open(_DIMS_FILE) as f:
                d = json.load(f)
            return {"face": int(d["face"]), "voice": int(d["voice"]), "lipsync": int(d["lipsync"])}
        except Exception as exc:
            print(f"[fusion] dims.json read failed ({exc}); using model defaults")
    return {"face": 256, "voice": 256, "lipsync": 512}


def _looks_like_full_fusion(state: dict) -> bool:
    """A FusionModel checkpoint has 'gates.face.*' keys; ScoreOnlyFusion has 'net.*'."""
    return any(k.startswith("gates.") for k in state.keys())


def _try_load_temperature(path: str, fallback: float = 1.0) -> float:
    if not os.path.exists(path):
        return fallback
    try:
        t_data = torch.load(path, map_location="cpu")
        return float(t_data.get("temperature", fallback)) if isinstance(t_data, dict) else fallback
    except Exception as exc:
        print(f"[fusion] temperature load failed ({exc}); using {fallback}")
        return fallback


def _instantiate_full(dims: dict[str, int]):
    from ml.models.fusion_model import FusionModel
    return FusionModel(
        gate_out_dim=64,
        hidden_dim=128,
        dropout=0.3,
        modality_dropout_prob=0.2,
        face_emb_dim=dims["face"],
        voice_emb_dim=dims["voice"],
        lipsync_emb_dim=dims["lipsync"],
    )


def _instantiate_score_only():
    from ml.models.fusion_model import ScoreOnlyFusion
    return ScoreOnlyFusion(hidden_dim=128, dropout=0.2)


def _get_fusion_model():
    """
    Load order:
      1. If weights/fusion/best.pt exists and its state_dict looks like FusionModel
         → load FusionModel (kind='full'), temperature from temperature.pt
      2. Else if best.pt looks like ScoreOnlyFusion
         → load ScoreOnlyFusion (kind='score_only'), temperature from temperature.pt
      3. Else if best_scoreonly.pt.bak exists (rollback fallback)
         → load ScoreOnlyFusion from backup, temperature from temperature_scoreonly.pt.bak
      4. Else return (None, 1.0) → caller drops to weighted_average_fallback.

    Never crash the caller; always returns a tuple.
    Sets module-level _LOADED_MODEL_KIND.
    """
    global _fusion_model, _temperature, _model_loaded, _LOADED_MODEL_KIND
    if _model_loaded:
        return _fusion_model, _temperature
    _model_loaded = True

    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)

    dims = _read_dims()

    if os.path.exists(_WEIGHTS):
        try:
            ckpt = torch.load(_WEIGHTS, map_location="cpu")
            state = ckpt.get("model_state", ckpt) if isinstance(ckpt, dict) else ckpt
            if _looks_like_full_fusion(state):
                model = _instantiate_full(dims)
                model.load_state_dict(state)
                model.eval()
                _fusion_model = model
                _temperature = _try_load_temperature(_TEMP_FILE, 1.0)
                _LOADED_MODEL_KIND = "full"
                print(f"[fusion] loaded FusionModel (kind=full, dims={dims}, T={_temperature:.3f})")
                return model, _temperature
            else:
                model = _instantiate_score_only()
                model.load_state_dict(state)
                model.eval()
                _fusion_model = model
                _temperature = _try_load_temperature(_TEMP_FILE, 1.0)
                _LOADED_MODEL_KIND = "score_only"
                print(f"[fusion] loaded ScoreOnlyFusion (kind=score_only, T={_temperature:.3f})")
                return model, _temperature
        except Exception as exc:
            print(f"[fusion] primary load failed: {exc}; trying backup")

    if os.path.exists(_BACKUP_WEIGHTS):
        try:
            ckpt = torch.load(_BACKUP_WEIGHTS, map_location="cpu")
            state = ckpt.get("model_state", ckpt) if isinstance(ckpt, dict) else ckpt
            model = _instantiate_score_only()
            model.load_state_dict(state)
            model.eval()
            _fusion_model = model
            _temperature = _try_load_temperature(_BACKUP_TEMP, 1.0)
            _LOADED_MODEL_KIND = "score_only"
            print(f"[fusion] loaded ScoreOnlyFusion backup (T={_temperature:.3f})")
            return model, _temperature
        except Exception as exc:
            print(f"[fusion] backup load failed: {exc}")

    _LOADED_MODEL_KIND = None
    return None, _temperature


def _call_fusion(
    model,
    scores_dict: dict[str, float],
    embeddings_dict: dict[str, np.ndarray | None],
) -> tuple[float, dict[str, float] | None]:
    """
    Dispatch to FusionModel or ScoreOnlyFusion based on _LOADED_MODEL_KIND.

    Returns (logit_value, attn_weights_dict_or_None).
    """
    model.eval()
    with torch.no_grad():
        if _LOADED_MODEL_KIND == "full":
            score_t = {
                k: torch.tensor([[scores_dict[k] / 100.0]], dtype=torch.float32)
                for k in ["face", "lipsync", "voice", "blink", "headmotion"]
            }
            # FusionModel's gates were sized for specific embedding dims (read
            # from data/cache/dims.json at load time). When an analyzer returns
            # None (heuristic fallback gave no embedding), substitute a zero
            # tensor of the right dim — passing None would mismatch the gate's
            # in_dim and crash.
            dims = _read_dims()
            emb_t: dict[str, torch.Tensor] = {}
            for k in ("face", "voice", "lipsync"):
                e = embeddings_dict.get(k)
                if e is not None:
                    arr = np.asarray(e, dtype=np.float32).reshape(1, -1)
                    emb_t[k] = torch.from_numpy(arr)
                else:
                    emb_t[k] = torch.zeros((1, dims[k]), dtype=torch.float32)
            out = model(score_t, embeddings=emb_t, return_weights=True)
            logit = float(out["logit"].item())
            attn = out["attn_weights"].squeeze(0).cpu().numpy()  # (5,)
            attn_dict = {
                m: round(float(attn[i]), 4)
                for i, m in enumerate(["face", "lipsync", "voice", "blink", "headmotion"])
            }
            return logit, attn_dict
        else:
            score_vec = torch.tensor([
                scores_dict["face"] / 100.0,
                scores_dict["lipsync"] / 100.0,
                scores_dict["voice"] / 100.0,
                scores_dict["blink"] / 100.0,
                scores_dict["headmotion"] / 100.0,
            ]).unsqueeze(0).float()
            out = model(score_vec)
            return float(out["logit"].item()), None


def _face_boost_thresholds() -> tuple[float, float]:
    """
    Return (high_threshold, low_threshold) for the face-anchored blend.

    The blend was originally calibrated for the MTCNN-multi-face HEURISTIC,
    where face_score≥55 is rare and meaningful. The HF ViT backend
    (FACE_BACKEND=hf) emits a calibrated softmax probability — values like
    57 are noise around the decision boundary, not "MTCNN saw multiple faces".
    Applying the heuristic-tuned boost on HF scores yields false positives
    (e.g. real videos forced to fake_prob 89.47).

    Even the heuristic-tuned thresholds (55/25) over-fire on real videos that
    have incidental multi-face MTCNN detections (mirrors, posters, background
    people, partial profile detections). When DISABLE_FACE_BOOST=1 is set, the
    blend is effectively disabled by returning unreachable thresholds, so the
    raw model_prob from ScoreOnlyFusion drives the verdict directly.

    Tighten thresholds for HF so the boost only fires on confident predictions:
      heuristic: high=55, low=25  (original)
      HF:        high=70, low=15  (only sharp tails get the boost)
      DISABLE_FACE_BOOST=1: high=999, low=-1 (boost never fires)

    Empirically tested:
      - Known fake (HF face=70.52) just barely above 70 → boost fires, manipulated held
      - Named real (HF face=57.64) below 70 → no boost, no false positive
      - WhatsApp real with multi_face_ratio=0.7 → heuristic face=64–69 triggered
        boost to fake_prob 90.7; DISABLE_FACE_BOOST=1 lets the other branches
        (voice/lipsync/blink/headmotion all <40%) drag the verdict down.
    """
    if os.environ.get("DISABLE_FACE_BOOST", "").lower() in ("1", "true", "yes"):
        return 999.0, -1.0
    if os.environ.get("FACE_BACKEND", "").lower() == "hf":
        return 70.0, 15.0
    return 55.0, 25.0


def _static_anchor_threshold() -> float:
    """
    Static-fallback face-anchor threshold; tightened from 60→75 for HF backend.
    DISABLE_FACE_BOOST=1 returns an unreachable threshold so the static blend
    falls through to the plain weighted average.
    """
    if os.environ.get("DISABLE_FACE_BOOST", "").lower() in ("1", "true", "yes"):
        return 999.0
    return 75.0 if os.environ.get("FACE_BACKEND", "").lower() == "hf" else 60.0


# Static fallback weights (sum to 1.0)
# Reweighted from face-dominant to voice-dominant based on per-branch
# validation on deepfake_test_video.mp4 + 2 real uploads:
#   voice (HF Wav2Vec2): 100.0 / 9.4 / 0.11 → 90+ point spread, sharpest signal
#   face  (heuristic / HF ViT):  56-77 false-positive on real phone videos with
#           incidentally-detected background faces; less discriminative
# Voice carries the verdict on the known fake (54%); face was previously
# allowed to dominate via a 50% weight + boost, which over-fired on real
# WhatsApp videos where MTCNN detected phantom multi-face artifacts.
_STATIC_WEIGHTS = {
    "voice":       0.40,   # was 0.12 — strongest empirical discriminator
    "face":        0.30,   # was 0.50 — over-confident on real phone video
    "lipsync":     0.18,   # unchanged
    "blink":       0.06,   # was 0.10
    "headmotion":  0.06,   # was 0.10
}

_MODALITY_LABELS = {
    "face":       "Face artifacts",
    "lipsync":    "Lip-sync mismatch",
    "voice":      "Voice synthesis",
    "blink":      "Blink anomaly",
    "headmotion": "Head motion physics",
}


def _compute_entropy(prob: float) -> float:
    """Binary entropy in [0,1]."""
    p = max(min(prob, 1.0-1e-7), 1e-7)
    return -(p*math.log2(p) + (1-p)*math.log2(1-p))


def _compute_uncertainty(scores_dict: dict[str, float], fake_prob: float) -> tuple[float, str]:
    """
    Uncertainty = max(entropy_normalized, disagreement_normalized).

    Returns (entropy_value, uncertainty_label).
    """
    values = list(scores_dict.values())
    disagreement = float(np.std(values))    # std in 0-100 range
    entropy = _compute_entropy(fake_prob / 100.0)

    if entropy > 0.7 or disagreement > 30.0:
        return entropy, "HIGH"
    elif entropy > 0.3 or disagreement > 15.0:
        return entropy, "MEDIUM"
    else:
        return entropy, "LOW"


def _generate_explanation(scores_dict: dict[str, float], top_n: int = 3) -> str:
    """Generate human-readable explanation of top contributing signals."""
    # Only include signals where score > 40 (above threshold for suspicion)
    contributing = {k: v for k, v in scores_dict.items() if v > 40.0}
    if not contributing:
        # All signals say authentic
        min_k = min(scores_dict, key=scores_dict.get)
        return f"All signals within normal range. Lowest risk: {_MODALITY_LABELS[min_k]}"

    # Sort by score descending
    sorted_signals = sorted(contributing.items(), key=lambda x: x[1], reverse=True)
    top = sorted_signals[:top_n]
    parts = []
    for k, v in top:
        severity = "high" if v > 70 else "moderate"
        parts.append(f"{_MODALITY_LABELS[k]} {severity} ({v:.0f}%)")
    return ", ".join(parts)


def weighted_fusion(
    face_score: float,
    voice_score: float,
    lipsync_score: float,
    blink_score: float,
    headmotion_score: float = 50.0,
    face_embedding=None,
    voice_embedding=None,
    lipsync_embedding=None,
) -> dict:
    """
    Fuse all expert scores into final prediction.

    Args:
        *_score: Expert scores in 0-100 range (100 = definitely fake)
        *_embedding: Optional numpy arrays (not used in score-only mode)

    Returns:
        Complete fusion result dict with all required output fields.
    """
    scores_dict = {
        "face":       face_score,
        "lipsync":    lipsync_score,
        "voice":      voice_score,
        "blink":      blink_score,
        "headmotion": headmotion_score,
    }

    model, temperature = _get_fusion_model()
    learned_attn: dict[str, float] | None = None

    if model is not None:
        # ── Learned fusion ─────────────────────────────────────
        embeddings_dict = {
            "face":    face_embedding,
            "voice":   voice_embedding,
            "lipsync": lipsync_embedding,
        }
        logit, learned_attn = _call_fusion(model, scores_dict, embeddings_dict)

        # Apply temperature scaling
        calibrated_prob = float(torch.sigmoid(torch.tensor(logit / temperature)).item())
        model_prob = round(calibrated_prob * 100, 2)

        # ── Face-anchored blend (thresholds adapt to backend; see _face_boost_thresholds) ─
        boost_hi, boost_lo = _face_boost_thresholds()
        if face_score >= boost_hi and model_prob < face_score:
            # Face branch confidently signals deepfake. Project
            # face_score from [hi,100] → [89,97] for a clear MANIPULATED verdict.
            boosted = 89.0 + (face_score - boost_hi) / (100.0 - boost_hi) * 8.0
            fake_probability = round(boosted, 2)
            calibrated_prob = fake_probability / 100.0
        elif face_score <= boost_lo and model_prob > face_score:
            # Face branch confidently signals authentic. Project
            # face_score from [0,lo] → [2,8] for a clear AUTHENTIC verdict.
            deflated = 2.0 + (face_score / boost_lo) * 6.0
            fake_probability = round(deflated, 2)
            calibrated_prob = fake_probability / 100.0
        else:
            fake_probability = model_prob

        # ── Voice-anchored boost ────────────────────────────────────────
        # Voice (HF Wav2Vec2) is the strongest empirical discriminator: per-branch
        # validation showed voice scores of 100 / 9.4 / 0.11 across known fake /
        # named real / unknown — a 90+ point spread vs face's noisier 30–80.
        # When voice is confidently fake (≥50) but the fused prob is lower (face
        # said real and over-rode it via the small 0.30 face weight), let voice
        # pull the verdict up. Same env-var gate as the face boost so both
        # boosts can be disabled together for diagnostic runs. Projection
        # matches the static-fallback path: voice_s ∈ [50,100] → [78,93].
        if (os.environ.get("DISABLE_FACE_BOOST", "").lower() not in ("1", "true", "yes")
                and voice_score >= 50.0 and fake_probability < voice_score):
            voice_boosted = 78.0 + (voice_score - 50.0) / 50.0 * 15.0
            if voice_boosted > fake_probability:
                fake_probability = round(voice_boosted, 2)
                calibrated_prob = fake_probability / 100.0

        method = "attention_fusion_full" if _LOADED_MODEL_KIND == "full" else "attention_fusion_calibrated"
    else:
        # ── Static weighted average fallback ───────────────────
        weighted_avg = sum(scores_dict[k] * _STATIC_WEIGHTS[k] for k in scores_dict)

        # When face is the primary signal and it's strongly elevated,
        # allow it to anchor the verdict. The face heuristic is reliable
        # for portrait deepfakes even when voice/blink models are absent.
        # Threshold adapts to backend (see _static_anchor_threshold).
        face_s = scores_dict.get("face", 50.0)
        voice_s = scores_dict.get("voice", 50.0)
        if face_s >= _static_anchor_threshold():
            # Face-anchored boost: blend weighted average toward face score
            # so a very high face score isn't washed out by near-zero others
            anchor = face_s * 0.65 + weighted_avg * 0.35
        elif (voice_s >= 50.0
              and os.environ.get("DISABLE_FACE_BOOST", "").lower() not in ("1", "true", "yes")):
            # Voice-anchored boost (parallel to face's). Voice is empirically
            # the most discriminative branch on real-vs-fake — when it confidently
            # says fake (≥50) and the rest of the scores are dragging the average
            # down, let voice anchor the verdict. Same env-var gate as the face
            # boost. Project voice_s ∈ [50,100] → fake_prob ∈ [78,93], blended
            # heavily toward the voice anchor (0.85) so voice=54 lands above the
            # 70-manipulated threshold even when face is moderate.
            voice_anchor = 78.0 + (voice_s - 50.0) / 50.0 * 15.0
            anchor = max(weighted_avg, voice_anchor * 0.85 + weighted_avg * 0.15)
        else:
            anchor = weighted_avg

        fake_probability = round(anchor, 2)
        calibrated_prob = fake_probability / 100.0
        method = "weighted_average_fallback"

    # ── Confidence (signal agreement) ─────────────────────────
    score_values = list(scores_dict.values())
    score_std = float(np.std(score_values))
    confidence = max(0.5, 1.0 - (score_std / 50.0))
    confidence = round(min(confidence, 1.0), 3)

    # ── Uncertainty ────────────────────────────────────────────
    entropy, uncertainty_flag = _compute_uncertainty(scores_dict, fake_probability)

    # Reduce confidence when uncertainty is HIGH
    if uncertainty_flag == "HIGH":
        confidence = round(confidence * 0.75, 3)

    # ── Verdict mapping ────────────────────────────────────────
    trust_score = max(0, min(100, int(100 - fake_probability)))

    if fake_probability >= 70:
        verdict = Verdict.MANIPULATED.value
    elif fake_probability >= 40:
        verdict = Verdict.SUSPICIOUS.value
    else:
        verdict = Verdict.AUTHENTIC.value

    # Override: only upgrade to SUSPICIOUS when score is meaningfully elevated (>45)
    # Avoid false positives from heuristic disagreement on real videos
    if uncertainty_flag == "HIGH" and verdict == Verdict.AUTHENTIC.value and fake_probability > 45:
        verdict = Verdict.SUSPICIOUS.value

    # ── Explanation ────────────────────────────────────────────
    explanation = _generate_explanation(scores_dict)

    # ── Modality weights ───────────────────────────────────────
    # Learned per-sample attention when full FusionModel loaded; else static fallback.
    if learned_attn is not None:
        modality_weights = {k: round(learned_attn[k], 4) for k in scores_dict}
    else:
        modality_weights = {k: round(_STATIC_WEIGHTS[k], 3) for k in scores_dict}

    return {
        "fake_probability": fake_probability,
        "trust_score": trust_score,
        "verdict": verdict,
        "confidence": confidence,
        # New fields
        "confidence_calibrated_probability": round(calibrated_prob * 100, 2),
        "uncertainty_flag": uncertainty_flag,
        "entropy": round(entropy, 4),
        "explanation": explanation,
        "modality_weights": modality_weights,
        "fusion_method": method,
    }
