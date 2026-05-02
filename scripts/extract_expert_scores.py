"""
Extract expert scores from all training/val videos and cache for fusion training.

Usage:
    python scripts/extract_expert_scores.py --manifest data/manifest.json
"""
from __future__ import annotations
import argparse, sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../services/api"))

import numpy as np
from tqdm import tqdm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=str, required=True)
    parser.add_argument("--output",   type=str, default="data/expert_scores")
    parser.add_argument("--splits",   type=str, nargs="+", default=["train", "val", "test"])
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    with open(args.manifest) as f:
        all_records = json.load(f)

    from scripts.predict import run_predict

    for split in args.splits:
        records = [r for r in all_records if r.get("split") == split]
        print(f"\nExtracting expert scores for split='{split}' ({len(records)} videos)")

        rows = []  # each row: [face, lipsync, voice, blink, headmotion, label]

        for rec in tqdm(records, desc=split):
            try:
                result = run_predict(rec["video_path"], verbose=False)
                ps = result["per_signal_scores"]
                row = [
                    ps["face_score"],
                    ps["lipsync_score"],
                    ps["voice_score"],
                    ps["blink_score"],
                    ps["headmotion_score"],
                    float(rec["label"]),
                ]
            except Exception as exc:
                print(f"  Error: {rec['video_path']}: {exc}")
                row = [50., 50., 50., 50., 50., float(rec["label"])]
            rows.append(row)

        arr = np.array(rows, dtype=np.float32)
        out_path = os.path.join(args.output, f"expert_scores_{split}.npy")
        np.save(out_path, arr)
        print(f"  Saved {arr.shape[0]} rows to {out_path}")
        n_fake = int(arr[:, 5].sum())
        print(f"  Real: {len(rows)-n_fake}  Fake: {n_fake}")


if __name__ == "__main__":
    main()
