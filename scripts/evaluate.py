"""
Evaluation Script — Cross-dataset metrics + ablation study.

Computes: Accuracy, Precision, Recall, F1, AUC-ROC, EER, ECE
Also runs cross-dataset generalization and ablation over modalities.

Usage:
    python scripts/evaluate.py --manifest data/manifest.json --split test
"""
from __future__ import annotations
import argparse, sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../services/api"))

import numpy as np
from tqdm import tqdm
from sklearn.metrics import roc_auc_score, roc_curve, confusion_matrix

from ml.training.trainer_utils import compute_metrics
from ml.calibration.calibrator import compute_ece, compute_eer


def evaluate_video(video_path):
    """Run full pipeline on one video and return scores dict."""
    try:
        from scripts.predict import run_predict
        result = run_predict(video_path, verbose=False)
        return result
    except Exception as exc:
        print(f"  Error on {video_path}: {exc}")
        return None


def run_ablation(probs_all, labels, modality_scores):
    """
    Ablation: what happens when we remove each modality?
    Uses static weighted average for comparison.
    """
    WEIGHTS = {
        "face":0.30, "lipsync":0.22, "voice":0.22, "blink":0.13, "headmotion":0.13
    }
    all_keys = list(WEIGHTS.keys())
    results = {}

    # Full model
    full_probs = np.array(probs_all) / 100.0
    results["all_modalities"] = compute_metrics(full_probs.tolist(), labels)
    results["all_modalities"]["ece"] = compute_ece(full_probs, np.array(labels))

    # Single modality
    for key in all_keys:
        probs = np.array(modality_scores[key]) / 100.0
        m = compute_metrics(probs.tolist(), labels)
        results[f"only_{key}"] = m

    # Leave-one-out
    for drop_key in all_keys:
        remaining_w = {k: v for k, v in WEIGHTS.items() if k != drop_key}
        total_w = sum(remaining_w.values())
        probs = []
        for i in range(len(labels)):
            p = sum(modality_scores[k][i] * remaining_w[k] for k in remaining_w) / (total_w * 100)
            probs.append(p)
        m = compute_metrics(probs, labels)
        results[f"without_{drop_key}"] = m

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=str, required=True)
    parser.add_argument("--split",    type=str, default="test")
    parser.add_argument("--max_samples", type=int, default=None)
    args = parser.parse_args()

    with open(args.manifest) as f:
        records = json.load(f)
    records = [r for r in records if r.get("split") == args.split]
    if args.max_samples:
        records = records[:args.max_samples]

    print(f"Evaluating {len(records)} videos from split='{args.split}'")

    all_probs, all_labels = [], []
    modality_scores = {k: [] for k in ["face","lipsync","voice","blink","headmotion"]}
    per_dataset = {}

    for rec in tqdm(records, desc="Evaluating"):
        result = evaluate_video(rec["video_path"])
        if result is None:
            continue

        prob = result["fake_probability"]
        label = rec["label"]
        all_probs.append(prob)
        all_labels.append(label)

        for k in modality_scores:
            modality_scores[k].append(result["per_signal_scores"].get(f"{k}_score", 50.0))

        ds = rec.get("dataset", "unknown")
        if ds not in per_dataset:
            per_dataset[ds] = {"probs":[], "labels":[]}
        per_dataset[ds]["probs"].append(prob)
        per_dataset[ds]["labels"].append(label)

    if len(all_probs) == 0:
        print("No results collected. Check pipeline.")
        return

    # ── Overall metrics ──────────────────────────────────────────
    probs_arr = np.array(all_probs) / 100.0
    labels_arr = np.array(all_labels)

    overall = compute_metrics(probs_arr.tolist(), labels_arr.tolist())
    ece = compute_ece(probs_arr, labels_arr)
    fpr, tpr, threshs = roc_curve(labels_arr, probs_arr)
    eer = compute_eer(fpr, tpr, threshs)
    cm = confusion_matrix(labels_arr, (probs_arr >= 0.5).astype(int))

    print("\n" + "="*60)
    print("OVERALL METRICS")
    print("="*60)
    for k, v in overall.items():
        print(f"  {k:<15} {v:.4f}")
    print(f"  {'ece':<15} {ece:.4f}")
    print(f"  {'eer':<15} {eer:.4f}")
    print(f"\nConfusion Matrix:\n{cm}")

    # ── Per-dataset breakdown ─────────────────────────────────────
    if len(per_dataset) > 1:
        print("\n" + "="*60)
        print("PER-DATASET BREAKDOWN")
        print("="*60)
        for ds, data in per_dataset.items():
            if len(data["probs"]) < 5:
                continue
            p = np.array(data["probs"]) / 100.0
            l = np.array(data["labels"])
            m = compute_metrics(p.tolist(), l.tolist())
            print(f"  {ds:<20} n={len(l):4d}  auc={m['auc_roc']:.4f}  f1={m['f1']:.4f}")

    # ── Ablation ─────────────────────────────────────────────────
    print("\n" + "="*60)
    print("ABLATION STUDY")
    print("="*60)
    ablation = run_ablation(all_probs, all_labels, modality_scores)
    for name, m in sorted(ablation.items()):
        auc = m.get("auc_roc", 0)
        f1  = m.get("f1", 0)
        ece_v = m.get("ece", 0)
        print(f"  {name:<30} auc={auc:.4f}  f1={f1:.4f}  ece={ece_v:.4f}")

    # ── Save results ─────────────────────────────────────────────
    output = {
        "overall": {**overall, "ece": ece, "eer": eer},
        "per_dataset": {
            ds: compute_metrics(
                (np.array(d["probs"])/100).tolist(), d["labels"]
            ) for ds, d in per_dataset.items() if len(d["probs"]) >= 5
        },
        "ablation": ablation,
        "n_samples": len(all_probs),
        "split": args.split,
    }
    out_path = f"data/eval_{args.split}_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
