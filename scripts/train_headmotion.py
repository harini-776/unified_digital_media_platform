"""
Train Head Motion Physics Classifier.

Uses MediaPipe FaceMesh to extract head pose (yaw/pitch/roll) time-series,
then computes physics features and trains XGBoost.

Usage:
    python scripts/train_headmotion.py --manifest data/manifest.json
"""
from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import yaml
import numpy as np
from tqdm import tqdm

from ml.models.headmotion_model import (
    HeadMotionClassifier,
    extract_headmotion_features,
)
from ml.training.trainer_utils import set_seed, compute_metrics


# MediaPipe 3D head pose estimation using solvePnP
# Reference face model points (from OpenCV/MediaPipe docs)
FACE_3D_MODEL = np.array([
    [0.0,   0.0,   0.0],     # Nose tip
    [0.0,  -330., -65.],     # Chin
    [-225., 170., -135.],    # Left eye corner
    [225.,  170., -135.],    # Right eye corner
    [-150., -150., -125.],   # Left mouth corner
    [150.,  -150., -125.],   # Right mouth corner
], dtype=np.float64)

# Corresponding MediaPipe landmark indices
FACE_2D_IDX = [1, 152, 263, 33, 287, 57]


def extract_pose_sequence(video_path: str, target_fps: float = 10.0) -> tuple[np.ndarray, ...]:
    """
    Extract yaw/pitch/roll time-series using MediaPipe + solvePnP.

    Returns: (yaw, pitch, roll) each shape (T,) in degrees, or empty arrays.
    """
    import cv2
    try:
        import mediapipe as mp
    except ImportError:
        return np.array([]), np.array([]), np.array([])

    mp_face = mp.solutions.face_mesh
    face_mesh = mp_face.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
    )

    cap = cv2.VideoCapture(video_path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step    = max(1, int(src_fps / target_fps))

    yaw_list, pitch_list, roll_list = [], [], []
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % step == 0:
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = face_mesh.process(rgb)

            if result.multi_face_landmarks:
                lm = result.multi_face_landmarks[0]
                face_2d = np.array([
                    [lm.landmark[i].x * w, lm.landmark[i].y * h]
                    for i in FACE_2D_IDX
                ], dtype=np.float64)

                cam_mat = np.array([
                    [w,  0, w / 2],
                    [0,  w, h / 2],
                    [0,  0, 1],
                ], dtype=np.float64)

                ok, rot_vec, _ = cv2.solvePnP(
                    FACE_3D_MODEL, face_2d, cam_mat, np.zeros((4, 1)),
                    flags=cv2.SOLVEPNP_ITERATIVE,
                )
                if ok:
                    rmat, _ = cv2.Rodrigues(rot_vec)
                    sy = np.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
                    if sy > 1e-6:
                        pitch = np.degrees(np.arctan2(-rmat[2, 0], sy))
                        yaw   = np.degrees(np.arctan2(rmat[2, 1], rmat[2, 2]))
                        roll  = np.degrees(np.arctan2(rmat[1, 0], rmat[0, 0]))
                    else:
                        pitch = np.degrees(np.arctan2(-rmat[2, 0], sy))
                        yaw   = 0.0
                        roll  = np.degrees(np.arctan2(-rmat[1, 2], rmat[1, 1]))

                    yaw_list.append(yaw)
                    pitch_list.append(pitch)
                    roll_list.append(roll)
                else:
                    yaw_list.append(0.0)
                    pitch_list.append(0.0)
                    roll_list.append(0.0)
            else:
                yaw_list.append(0.0)
                pitch_list.append(0.0)
                roll_list.append(0.0)

        frame_idx += 1

    cap.release()
    face_mesh.close()

    return (
        np.array(yaw_list, dtype=np.float32),
        np.array(pitch_list, dtype=np.float32),
        np.array(roll_list, dtype=np.float32),
    )


def build_feature_matrix(manifest_path, split, target_fps, cache_dir):
    import hashlib
    with open(manifest_path) as f:
        records = json.load(f)
    records = [r for r in records if r.get("split") == split]

    X, y = [], []
    os.makedirs(cache_dir, exist_ok=True)

    for rec in tqdm(records, desc=f"[{split}] Pose extraction"):
        ck = hashlib.md5(rec["video_path"].encode()).hexdigest()[:12]
        cache_f = os.path.join(cache_dir, f"headmotion_{ck}.npy")

        if os.path.exists(cache_f):
            feat_vec = np.load(cache_f)
        else:
            yaw, pitch, roll = extract_pose_sequence(rec["video_path"], target_fps)
            if len(yaw) < 5:
                continue
            feats = extract_headmotion_features(yaw, pitch, roll, fps=target_fps)
            feat_vec = feats.to_array()
            np.save(cache_f, feat_vec)

        X.append(feat_vec)
        y.append(rec["label"])

    return np.array(X, dtype=np.float32), np.array(y, dtype=int)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=str, required=True)
    parser.add_argument("--config",   type=str, default="ml/configs/config.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    hc = cfg["headmotion"]
    set_seed(cfg["seed"])
    target_fps = cfg["data"]["target_fps"]
    cache_dir  = cfg["data"]["cache_dir"]

    X_train, y_train = build_feature_matrix(args.manifest, "train", target_fps, cache_dir)
    X_val,   y_val   = build_feature_matrix(args.manifest, "val",   target_fps, cache_dir)

    print(f"Train: {X_train.shape[0]}  Val: {X_val.shape[0]}")

    clf = HeadMotionClassifier(backend=hc["feature_method"].replace("pose_timeseries", "xgboost"))
    clf.fit(X_train, y_train)

    val_probs = clf.predict_proba(X_val)[:, 1]
    m = compute_metrics(val_probs.tolist(), y_val.tolist())
    print(f"Val metrics: auc={m['auc_roc']:.4f}  f1={m['f1']:.4f}")

    os.makedirs(hc["checkpoint_dir"], exist_ok=True)
    path = os.path.join(hc["checkpoint_dir"], "headmotion_classifier.joblib")
    clf.save(path)
    print(f"Saved to {path}")


if __name__ == "__main__":
    main()
