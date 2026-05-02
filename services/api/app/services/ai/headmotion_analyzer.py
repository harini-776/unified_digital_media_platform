"""
Head Motion Physics Branch — Production Inference.

New module: uses MediaPipe + solvePnP for pose estimation,
XGBoost on physics features for classification.
"""
from __future__ import annotations
import os, sys, cv2, numpy as np
from app.core.config import get_settings

settings = get_settings()

_WEIGHTS = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "../../../../../weights/headmotion/headmotion_classifier.joblib"
))

_hm_clf = None
_clf_loaded = False

FACE_3D_MODEL = np.array([
    [0.,0.,0.],[0.,-330.,-65.],[-225.,170.,-135.],
    [225.,170.,-135.],[-150.,-150.,-125.],[150.,-150.,-125.],
], dtype=np.float64)
FACE_2D_IDX = [1, 152, 263, 33, 287, 57]


def _get_hm_clf():
    global _hm_clf, _clf_loaded
    if _clf_loaded:
        return _hm_clf
    _clf_loaded = True
    if not os.path.exists(_WEIGHTS):
        return None
    try:
        root = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../../../"))
        if root not in sys.path:
            sys.path.insert(0, root)
        from ml.models.headmotion_model import HeadMotionClassifier
        clf = HeadMotionClassifier("xgboost")
        clf.load(_WEIGHTS)
        _hm_clf = clf
        return clf
    except Exception as exc:
        print(f"[headmotion] model load failed: {exc}")
        return None


def _extract_pose(frame_paths, target_fps=10.0):
    # MediaPipe 0.10+ removed mp.solutions — gracefully fall back to heuristic
    try:
        import mediapipe as mp
        mp_face_mesh_mod = getattr(mp, "solutions", None)
        if mp_face_mesh_mod is None:
            return np.array([]), np.array([]), np.array([])
        face_mesh_cls = getattr(mp_face_mesh_mod, "face_mesh", None)
        if face_mesh_cls is None:
            return np.array([]), np.array([]), np.array([])
        face_mesh = face_mesh_cls.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True)
    except Exception:
        return np.array([]), np.array([]), np.array([])
    yaw_l, pitch_l, roll_l = [], [], []

    for path in frame_paths:
        img = cv2.imread(path)
        if img is None:
            yaw_l.append(0.); pitch_l.append(0.); roll_l.append(0.); continue
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        result = face_mesh.process(rgb)
        if result.multi_face_landmarks:
            lm = result.multi_face_landmarks[0]
            face_2d = np.array([[lm.landmark[i].x*w, lm.landmark[i].y*h]
                                 for i in FACE_2D_IDX], dtype=np.float64)
            cam_mat = np.array([[w,0,w/2],[0,w,h/2],[0,0,1]], dtype=np.float64)
            ok, rv, _ = cv2.solvePnP(FACE_3D_MODEL, face_2d, cam_mat, np.zeros((4,1)),
                                      flags=cv2.SOLVEPNP_ITERATIVE)
            if ok:
                rm, _ = cv2.Rodrigues(rv)
                sy = np.sqrt(rm[0,0]**2+rm[1,0]**2)
                if sy>1e-6:
                    pitch = np.degrees(np.arctan2(-rm[2,0], sy))
                    yaw   = np.degrees(np.arctan2(rm[2,1], rm[2,2]))
                    roll  = np.degrees(np.arctan2(rm[1,0], rm[0,0]))
                else:
                    pitch=np.degrees(np.arctan2(-rm[2,0],sy)); yaw=0.; roll=np.degrees(np.arctan2(-rm[1,2],rm[1,1]))
                yaw_l.append(yaw); pitch_l.append(pitch); roll_l.append(roll)
            else:
                yaw_l.append(0.); pitch_l.append(0.); roll_l.append(0.)
        else:
            yaw_l.append(0.); pitch_l.append(0.); roll_l.append(0.)

    face_mesh.close()
    return np.array(yaw_l,dtype=np.float32), np.array(pitch_l,dtype=np.float32), np.array(roll_l,dtype=np.float32)


def _heuristic_headmotion(frame_paths):
    """Simple head motion variance heuristic."""
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    positions = []
    for path in frame_paths[:40]:
        img = cv2.imread(path)
        if img is None: continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        if len(faces) > 0:
            x,y,w,h = max(faces, key=lambda f:f[2]*f[3])
            positions.append([x+w/2, y+h/2])

    if len(positions) < 3:
        return {"headmotion_score":50.0,"details":{"note":"Insufficient face detections"}}

    arr = np.array(positions)
    motion_std = float(np.std(arr, axis=0).mean())

    # Deepfakes tend to have unnaturally frozen or jittery motion
    # Natural: motion_std 1-40px (short clips naturally have less motion).
    # Frozen (<0.5px) or extreme jitter (>80px) = suspicious
    if motion_std < 0.5:
        score = 55.0   # completely frozen head — suspicious
    elif motion_std < 1.5:
        score = 25.0   # minimal motion — slight suspicion only
    elif motion_std > 80.0:
        score = 60.0   # extreme jitter — suspicious
    else:
        score = 12.0   # normal range

    # Check for sudden jumps (temporal discontinuity) — only penalise significant jumps
    deltas = np.linalg.norm(np.diff(arr, axis=0), axis=1)
    if len(deltas) > 2:
        jump_ratio = float(np.sum(deltas > 50) / len(deltas))
        score = min(100.0, score + jump_ratio * 35)

    return {"headmotion_score":round(score,2),
            "details":{"method":"heuristic_motion_std","motion_std":round(motion_std,4)}}


def analyze_headmotion(frame_paths: list[str]) -> dict:
    """
    Analyze head motion for deepfake physics artifacts.
    Returns headmotion_score (0=authentic, 100=fake) and details.
    """
    if len(frame_paths) < 5:
        return {"headmotion_score":50.0,"details":{"note":"Too few frames"}}

    clf = _get_hm_clf()
    if clf is None:
        return _heuristic_headmotion(frame_paths)

    yaw, pitch, roll = _extract_pose(frame_paths, target_fps=10.0)
    if len(yaw) < 5:
        return _heuristic_headmotion(frame_paths)

    root = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../../../"))
    if root not in sys.path:
        sys.path.insert(0, root)
    from ml.models.headmotion_model import extract_headmotion_features

    feats = extract_headmotion_features(yaw, pitch, roll, fps=10.0)
    feat_vec = feats.to_array().reshape(1, -1)

    try:
        proba = clf.predict_proba(feat_vec)[0, 1]
    except Exception:
        return _heuristic_headmotion(frame_paths)

    return {
        "headmotion_score": round(proba*100, 2),
        "details": {
            "method":"ml_xgboost_pose",
            "yaw_range": round(feats.yaw_range, 2),
            "velocity_mean": round(feats.velocity_mean, 4),
            "smoothness": round(feats.smoothness_score, 4),
            "has_frozen": round(feats.has_frozen_segment, 4),
            "frames_analyzed": len(yaw),
        }
    }
