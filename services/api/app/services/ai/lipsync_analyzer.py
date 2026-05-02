"""
Lip-Sync Branch — Production Inference.

Upgrades from simple cross-correlation to trained LipSyncModel.
Falls back to correlation heuristic if weights unavailable.
"""
from __future__ import annotations
import os, sys, cv2, hashlib, subprocess, numpy as np, torch
import librosa
from app.core.config import get_settings

settings = get_settings()

_WEIGHTS = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "../../../../../weights/lipsync/best.pt"
))

N_MELS = 80
_lipsync_model = None
_model_loaded = False


def _get_lipsync_model():
    global _lipsync_model, _model_loaded
    if _model_loaded:
        return _lipsync_model
    _model_loaded = True
    if not os.path.exists(_WEIGHTS):
        return None
    try:
        root = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../../../"))
        if root not in sys.path:
            sys.path.insert(0, root)
        from ml.models.lipsync_model import LipSyncModel
        model = LipSyncModel(embedding_dim=512)
        ckpt = torch.load(_WEIGHTS, map_location="cpu")
        model.load_state_dict(ckpt["model_state"])
        model.eval().to(settings.model_device)
        _lipsync_model = model
        return model
    except Exception as exc:
        print(f"[lipsync] model load failed: {exc}")
        return None


def _get_mouth_crop(img_cv):
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, 1.3, 5)
    if len(faces) == 0:
        return None
    x,y,w,h = max(faces, key=lambda f: f[2]*f[3])
    mouth_y = y + int(h*0.6)
    crop = img_cv[mouth_y:y+h, x:x+w]
    return cv2.resize(crop, (96,64)) if crop.size>0 else None


def _get_mouth_openness_mediapipe(frame_paths):
    """
    Use MediaPipe FaceMesh to extract precise mouth-open distance per frame.
    Returns list of (mouth_open_ratio, lip_variance) per frame.
    Falls back to Haar cascade if MediaPipe unavailable.
    """
    # MediaPipe lip landmarks: upper lip top=13, lower lip bottom=14
    # Mouth corners: left=78, right=308
    UPPER_LIP = [13, 312, 311, 310, 415, 308]
    LOWER_LIP = [14, 317, 402, 318, 324, 78]
    CORNER_L, CORNER_R = 78, 308

    try:
        import mediapipe as mp
        mp_face = getattr(mp, "solutions", None)
        if mp_face is None:
            return None
        face_mesh = mp_face.face_mesh.FaceMesh(
            static_image_mode=True, max_num_faces=1, refine_landmarks=True)
    except Exception:
        return None

    openness = []
    for path in frame_paths[:40]:
        img = cv2.imread(path)
        if img is None:
            openness.append(0.0); continue
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        result = face_mesh.process(rgb)
        if result.multi_face_landmarks:
            lm = result.multi_face_landmarks[0].landmark
            # Mouth height = avg distance between upper and lower lip
            upper_y = np.mean([lm[i].y * h for i in UPPER_LIP])
            lower_y = np.mean([lm[i].y * h for i in LOWER_LIP])
            mouth_h = abs(lower_y - upper_y)
            # Mouth width for normalization
            mouth_w = abs(lm[CORNER_R].x * w - lm[CORNER_L].x * w) + 1e-6
            openness.append(float(mouth_h / mouth_w))
        else:
            openness.append(0.0)

    face_mesh.close()
    return openness if len(openness) > 0 else None


def _heuristic_lipsync(frame_paths, audio_path):
    """
    Improved lipsync heuristic using MediaPipe mouth landmarks + audio RMS correlation.

    AI deepfakes often show:
      - Mouth barely opens or has unnatural range (GAN doesn't learn full articulation)
      - Very regular/robotic mouth motion (periodic, not driven by speech rhythm)
      - Poor correlation between mouth openness and audio energy

    Real videos show:
      - Natural mouth opening proportional to vowel sounds
      - Irregular, speech-driven mouth motion
      - Good correlation with audio RMS peaks
    """
    if audio_path is None or len(frame_paths) < 5:
        return {"lipsync_score": 50.0, "embedding": None,
                "details": {"note": "No audio or too few frames"}}

    # Try MediaPipe-based mouth tracking first
    openness = _get_mouth_openness_mediapipe(frame_paths)

    # Fall back to Haar cascade if MediaPipe failed
    if openness is None:
        openness = []
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        for path in frame_paths[:30]:
            img = cv2.imread(path)
            if img is None:
                openness.append(0.0); continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.3, 5)
            if len(faces) > 0:
                x,y,w,h = max(faces, key=lambda f: f[2]*f[3])
                mouth_roi = gray[y+int(h*0.6):y+h, x:x+w]
                if mouth_roi.size > 0:
                    openness.append(float(np.var(cv2.Laplacian(mouth_roi, cv2.CV_64F))))
                else:
                    openness.append(0.0)
            else:
                openness.append(0.0)

    try:
        waveform, sr = librosa.load(audio_path, sr=16000, mono=True)
        hop = int(sr / max(1, len(openness) / max(1, len(waveform) / sr)))
        hop = max(256, min(hop, int(sr * 0.5)))
        rms = librosa.feature.rms(y=waveform, hop_length=hop)[0]
    except Exception:
        return {"lipsync_score": 50.0, "embedding": None,
                "details": {"note": "Audio load failed"}}

    min_len = min(len(openness), len(rms))
    if min_len < 4:
        return {"lipsync_score": 50.0, "embedding": None,
                "details": {"note": "Insufficient data"}}

    m = np.array(openness[:min_len], dtype=np.float32)
    a = rms[:min_len].astype(np.float32)

    # ── Signal 1: Audio-visual correlation ───────────────────────────────────
    corr = 0.0
    if m.std() > 1e-6 and a.std() > 1e-6:
        corr = float(np.corrcoef((m - m.mean()) / m.std(),
                                  (a - a.mean()) / a.std())[0, 1])

    detected_ratio = float(np.sum(m > 1e-4) / len(m))

    # ── Signal 2: Mouth motion regularity ────────────────────────────────────
    # Deepfakes often have robotic, periodic mouth motion
    # Compute autocorrelation of mouth openness: high periodicity → suspicious
    if len(m) >= 8 and m.std() > 1e-6:
        m_norm = (m - m.mean()) / (m.std() + 1e-6)
        acf_lags = [np.corrcoef(m_norm[:-k], m_norm[k:])[0,1]
                    for k in range(1, min(6, len(m)//2))]
        periodicity = float(np.max(np.abs(acf_lags))) if acf_lags else 0.0
    else:
        periodicity = 0.0

    # ── Signal 3: Mouth range (deepfakes under-open mouth) ───────────────────
    mouth_range = float(m.max() - m.min()) if m.max() > 1e-4 else 0.0
    # Very low range on talking video = mouth barely opens = suspicious
    if detected_ratio > 0.3 and mouth_range < 0.05:
        range_score = 60.0
    elif detected_ratio > 0.3 and mouth_range < 0.12:
        range_score = 35.0
    else:
        range_score = 10.0

    # ── Combine ───────────────────────────────────────────────────────────────
    if detected_ratio < 0.25:
        # Too few mouth detections — rely on audio only signal
        score = 35.0
    else:
        # Correlation: high positive corr → real (synced); low/negative → suspicious
        if corr > 0.45:
            corr_score = 8.0
        elif corr > 0.20:
            corr_score = 20.0
        elif corr > -0.10:
            corr_score = 40.0
        else:
            corr_score = 60.0

        periodicity_score = min(70.0, periodicity * 80.0)
        score = 0.45 * corr_score + 0.30 * range_score + 0.25 * periodicity_score

    score = round(float(np.clip(score, 0, 100)), 2)

    return {
        "lipsync_score": score,
        "embedding": None,
        "details": {
            "method": "heuristic_mediapipe_av",
            "av_correlation": round(corr, 4),
            "mouth_detection_ratio": round(detected_ratio, 3),
            "mouth_range": round(mouth_range, 4),
            "periodicity": round(periodicity, 4),
        }
    }


def analyze_lipsync(frame_paths: list[str], audio_path: str | None) -> dict:
    """
    Analyze lip-audio synchronization.
    Returns: lipsync_score (0=synced/authentic, 100=desync/fake), embedding, details.
    """
    if audio_path is None:
        return {"lipsync_score":50.0,"embedding":None,"details":{"note":"No audio"}}

    model = _get_lipsync_model()
    if model is None:
        return _heuristic_lipsync(frame_paths, audio_path)

    device = torch.device(settings.model_device)

    # Build mouth sequence
    mouth_crops = []
    for path in frame_paths[:16]:
        img_cv = cv2.imread(path)
        if img_cv is None:
            continue
        crop = _get_mouth_crop(img_cv)
        if crop is not None:
            mouth_crops.append(crop)

    if len(mouth_crops) < 4:
        return _heuristic_lipsync(frame_paths, audio_path)

    while len(mouth_crops) < 16:
        mouth_crops.append(mouth_crops[-1])
    mouth_arr = np.stack(mouth_crops[:16]).transpose(0,3,1,2)  # (T,C,H,W)
    mouth_t = torch.from_numpy(mouth_arr).float().unsqueeze(0)/255.0  # (1,T,C,H,W)

    # Build mel spectrogram
    try:
        waveform, sr = librosa.load(audio_path, sr=16000, mono=True, duration=2.0)
        mel = librosa.feature.melspectrogram(y=waveform, sr=sr, n_mels=N_MELS)
        mel_db = librosa.power_to_db(mel+1e-6, ref=np.max)
        mel_db = (mel_db - mel_db.mean()) / (mel_db.std()+1e-6)
        if mel_db.shape[1] >= 128:
            mel_db = mel_db[:,:128]
        else:
            mel_db = np.pad(mel_db, ((0,0),(0,128-mel_db.shape[1])))
        mel_t = torch.from_numpy(mel_db[np.newaxis].astype(np.float32)).unsqueeze(0)
    except Exception:
        return _heuristic_lipsync(frame_paths, audio_path)

    model.eval()
    with torch.no_grad():
        out = model(mel_t.to(device), mouth_t.to(device))
        prob = torch.sigmoid(out["logit"]).item()
        cos_dist = model.compute_cosine_distance(
            out["audio_embedding"], out["video_embedding"]
        ).item()

    # Combine logit prob and cosine distance
    lipsync_score = round(prob * 100, 2)

    return {
        "lipsync_score": lipsync_score,
        "embedding": out["audio_embedding"].cpu().numpy()[0],
        "details": {
            "method":"ml_syncnet_style",
            "fake_probability": round(prob*100,2),
            "cosine_av_distance": round(cos_dist, 4),
            "mouth_frames_used": len(mouth_crops),
        }
    }
