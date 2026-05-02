"""
Train Blink Classifier using MediaPipe EAR time-series features.

Processes all videos in manifest, extracts blink features per video,
then fits XGBoost classifier.

Usage:
    python scripts/train_blink.py --manifest data/manifest.json --config ml/configs/config.yaml
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

from ml.models.blink_model import (
    BlinkClassifier,
    BlinkFeatures,
    extract_blink_features,
    compute_ear,
    LEFT_EYE_IDX,
    RIGHT_EYE_IDX,
)
from ml.training.trainer_utils import set_seed, compute_metrics


def extract_ear_sequence_mediapipe(video_path: str, target_fps: float = 10.0) -> list[float]:
    """
    Extract EAR time-series from video using MediaPipe FaceMesh.

    Returns list of mean(left_ear, right_ear) per frame, or [] on failure.
    """
    import cv2
    try:
        import mediapipe as mp
    except ImportError:
        return []

    mp_face = mp.solutions.face_mesh
    face_mesh = mp_face.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
    )

    cap = cv2.VideoCapture(video_path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(src_fps / target_fps))

    ear_seq = []
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % step == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = face_mesh.process(rgb)
            if result.multi_face_landmarks:
                lm = result.multi_face_landmarks[0]
                h, w = frame.shape[:2]
                pts = np.array([[lm.landmark[i].x * w, lm.landmark[i].y * h]
                                for i in range(len(lm.landmark))])
                left_ear  = compute_ear(pts, LEFT_EYE_IDX)
                right_ear = compute_ear(pts, RIGHT_EYE_IDX)
                ear_seq.append((left_ear + right_ear) / 2.0)
            else:
                ear_seq.append(0.25)  # neutral fallback
        frame_idx += 1

    cap.release()
    face_mesh.close()
    return ear_seq


def build_feature_matrix(
    manifest_path: str,
    split: str,
    target_fps: float,
    cache_dir: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract features for all videos in split."""
    import hashlib

    with open(manifest_path) as f:
        records = json.load(f)
    records = [r for r in records if r.get("split") == split]

    X, y = [], []
    os.makedirs(cache_dir, exist_ok=True)

    for rec in tqdm(records, desc=f"[{split}] EAR extraction"):
        cache_key = hashlib.md5(rec["video_path"].encode()).hexdigest()[:12]
        feat_cache = os.path.join(cache_dir, f"blink_{cache_key}.npy")

        if os.path.exists(feat_cache):
            feat_vec = np.load(feat_cache)
        else:
            ear_seq = extract_ear_sequence_mediapipe(rec["video_path"], target_fps)
            if len(ear_seq) < 10:
                continue
            feats = extract_blink_features(ear_seq, fps=target_fps)
            feat_vec = feats.to_array()
            np.save(feat_cache, feat_vec)

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

    bc = cfg["blink"]
    set_seed(cfg["seed"])

    target_fps = cfg["data"]["target_fps"]
    cache_dir  = cfg["data"]["cache_dir"]

    print("Extracting training features...")
    X_train, y_train = build_feature_matrix(args.manifest, "train", target_fps, cache_dir)
    print(f"Train: {X_train.shape[0]} samples")

    print("Extracting validation features...")
    X_val, y_val = build_feature_matrix(args.manifest, "val", target_fps, cache_dir)
    print(f"Val:   {X_val.shape[0]} samples")

    clf = BlinkClassifier(backend=bc["classifier"])
    clf.fit(X_train, y_train)

    val_probs = clf.predict_proba(X_val)[:, 1]
    metrics = compute_metrics(val_probs.tolist(), y_val.tolist())
    print(f"Val metrics: auc={metrics['auc_roc']:.4f}  f1={metrics['f1']:.4f}")

    os.makedirs(bc["checkpoint_dir"], exist_ok=True)
    model_path = os.path.join(bc["checkpoint_dir"], "blink_classifier.joblib")
    clf.save(model_path)
    print(f"Saved to {model_path}")


if __name__ == "__main__":
    main()
