"""
Eye Blink Branch — Production Inference.

Upgrades from Haar cascade binary detection to:
  - MediaPipe FaceMesh for precise EAR time-series
  - XGBoost classifier on 14-dimensional blink feature vector
  - Falls back to heuristic if weights unavailable
"""
from __future__ import annotations
import os, sys, cv2, numpy as np, torch
from app.core.config import get_settings

settings = get_settings()

_WEIGHTS = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "../../../../../weights/blink/blink_classifier.joblib"
))

_blink_clf = None
_clf_loaded = False


def _get_blink_clf():
    global _blink_clf, _clf_loaded
    if _clf_loaded:
        return _blink_clf
    _clf_loaded = True
    if not os.path.exists(_WEIGHTS):
        return None
    try:
        root = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../../../"))
        if root not in sys.path:
            sys.path.insert(0, root)
        from ml.models.blink_model import BlinkClassifier
        clf = BlinkClassifier("xgboost")
        clf.load(_WEIGHTS)
        _blink_clf = clf
        return clf
    except Exception as exc:
        print(f"[blink] model load failed: {exc}")
        return None


def _compute_ear(pts, idxs):
    p = pts[list(idxs)]
    return (np.linalg.norm(p[1]-p[5])+np.linalg.norm(p[2]-p[4]))/(2*np.linalg.norm(p[0]-p[3])+1e-6)


LEFT_EYE  = (362, 385, 387, 263, 373, 380)
RIGHT_EYE = (33,  160, 158, 133, 153, 144)


def _extract_ear_sequence(frame_paths, target_fps=10.0):
    # MediaPipe 0.10+ removed mp.solutions — gracefully fall back to Haar cascade
    try:
        import mediapipe as mp
        mp_face_mesh_mod = getattr(mp, "solutions", None)
        if mp_face_mesh_mod is None:
            return []
        face_mesh_cls = getattr(mp_face_mesh_mod, "face_mesh", None)
        if face_mesh_cls is None:
            return []
        face_mesh = face_mesh_cls.FaceMesh(
            static_image_mode=True, max_num_faces=1, refine_landmarks=True
        )
    except Exception:
        return []

    ear_seq = []
    for path in frame_paths:
        img = cv2.imread(path)
        if img is None:
            ear_seq.append(0.25); continue
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        result = face_mesh.process(rgb)
        if result.multi_face_landmarks:
            lm = result.multi_face_landmarks[0]
            pts = np.array([[lm.landmark[i].x*w, lm.landmark[i].y*h]
                            for i in range(len(lm.landmark))])
            left  = _compute_ear(pts, LEFT_EYE)
            right = _compute_ear(pts, RIGHT_EYE)
            ear_seq.append((left+right)/2.0)
        else:
            ear_seq.append(0.25)

    face_mesh.close()
    return ear_seq


def _heuristic_blink(frame_paths):
    """Original Haar cascade fallback."""
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    eye_cascade  = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    eyes_detected, face_positions = [], []

    for path in frame_paths[:40]:
        img = cv2.imread(path)
        if img is None: continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        if len(faces) > 0:
            x,y,w,h = max(faces, key=lambda f:f[2]*f[3])
            face_positions.append([x+w/2, y+h/2])
            eyes = eye_cascade.detectMultiScale(gray[y:y+h,x:x+w], 1.1, 5)
            eyes_detected.append(len(eyes))
        else:
            eyes_detected.append(0)

    if len(eyes_detected) < 5:
        return {"blink_score":50.0,"details":{"note":"Insufficient face detections"}}

    eyes_arr = np.array(eyes_detected)
    blink_frames = np.where(eyes_arr==0)[0]
    blink_count = 0
    if len(blink_frames)>0:
        gaps = np.diff(blink_frames)
        blink_count = int(np.sum(gaps>2))+1

    head_motion_std = 0.0
    if len(face_positions)>1:
        fa = np.array(face_positions)
        head_motion_std = float(np.std(fa,axis=0).mean())

    # Duration based on actual face detection frames (2 fps sampling)
    dur = len(eyes_detected) / 2.0
    # Normal blink rate: ~15-20 blinks/min = 0.25-0.33 per second
    expected = dur * (17.0 / 60.0)
    score = 0.0

    # Need ≥8 seconds to reliably judge blink rate — short clips are too noisy
    if dur >= 8.0:
        if blink_count == 0:
            # Zero blinks in >8s is a strong deepfake indicator
            score += 65.0
        elif expected > 0:
            ratio = blink_count / expected
            if ratio < 0.3:
                # Severely under-blinking (< 30% of normal rate)
                score += 50.0
            elif ratio < 0.6:
                # Moderately under-blinking
                score += 30.0
            elif ratio > 4.0:
                # Over-blinking (jittery GAN artefact)
                score += 25.0
    elif dur >= 4.0:
        # Medium clips: only flag clearly abnormal patterns
        if blink_count == 0 and expected >= 1.5:
            score += 30.0
        elif expected > 0 and blink_count / expected < 0.2:
            score += 20.0

    # Frozen eye count across frames (deepfake eyes don't vary naturally)
    if float(np.std(eyes_arr)) < 0.1 and dur > 3:
        score += 15.0
    # Completely frozen head position
    if head_motion_std < 0.5 and dur > 3:
        score += 10.0

    return {"blink_score": min(score, 100.0), "details": {
        "method": "heuristic_haar",
        "blink_count": blink_count,
        "expected_blinks": round(expected, 1),
        "head_motion_std": round(head_motion_std, 5),
    }}


def analyze_blinks(frame_paths: list[str]) -> dict:
    """
    Analyze blink patterns using MediaPipe EAR + XGBoost classifier.
    Returns blink_score (0=authentic, 100=fake) and details.
    """
    if len(frame_paths) < 5:
        return {"blink_score":50.0,"details":{"note":"Too few frames"}}

    clf = _get_blink_clf()
    if clf is None:
        return _heuristic_blink(frame_paths)

    ear_seq = _extract_ear_sequence(frame_paths, target_fps=10.0)
    if len(ear_seq) < 10:
        return _heuristic_blink(frame_paths)

    root = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../../../"))
    if root not in sys.path:
        sys.path.insert(0, root)
    from ml.models.blink_model import extract_blink_features

    feats = extract_blink_features(ear_seq, fps=10.0)
    feat_vec = feats.to_array().reshape(1, -1)

    try:
        proba = clf.predict_proba(feat_vec)[0, 1]
    except Exception:
        return _heuristic_blink(frame_paths)

    blink_score = round(proba * 100, 2)
    return {
        "blink_score": blink_score,
        "details": {
            "method":"ml_xgboost_ear",
            "blink_rate_per_min": round(feats.blink_rate_per_min, 2),
            "ear_mean": round(feats.ear_mean, 4),
            "ibi_cv": round(feats.ibi_cv, 4),
            "frames_analyzed": len(ear_seq),
        }
    }
