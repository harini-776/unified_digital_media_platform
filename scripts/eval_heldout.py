"""
Non-blocking diagnostic table comparing ScoreOnlyFusion vs FusionModel verdicts
on a wider asset set than the gate uses.

The quality gate (scripts/verify_pipeline.py) only checks deepfake_test_video.mp4
and exists to trigger auto-rollback on regression. This script is meant to be
run *after* the gate (with whichever model survived rollback) to give the
thesis a per-asset picture: how do the two models compare across multiple
real videos and the known fake?

Output: markdown table to stdout + a JSON sidecar at outputs/eval_heldout_<ts>.json
with full per-asset scores for both models.

When B-4b lands (real labeled fakes), the held-out fakes get added to the
asset list. Until then, the negatives-only output is enough to see whether
the FusionModel is at least no worse on real videos.

Run:
    FACE_BACKEND=hf VOICE_BACKEND=hf .venv/bin/python scripts/eval_heldout.py
"""
from __future__ import annotations

import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
sys.path.insert(0, os.path.join(REPO_ROOT, "services/api"))
sys.path.insert(0, REPO_ROOT)

# Reuse the verify_pipeline helpers — no need to duplicate the model-kind
# probing or the rename-and-reload dance.
from verify_pipeline import (   # noqa: E402
    KNOWN_FAKE,
    UPLOADS_DIR,
    PRIMARY_WEIGHTS,
    BACKUP_WEIGHTS,
    VERDICT_SEVERITY,
    _run_with_kind,
)

# How many uploads to sample beyond KNOWN_FAKE. Spread across the lexically
# sorted upload list so we don't bias toward early/late filenames.
N_UPLOAD_SAMPLES = 4


def pick_assets() -> list[str]:
    """Return the list of video paths to evaluate. Always includes KNOWN_FAKE
    plus N spread samples from services/api/uploads/."""
    assets = [KNOWN_FAKE]
    if os.path.isdir(UPLOADS_DIR):
        files = sorted(f for f in os.listdir(UPLOADS_DIR)
                       if f.lower().endswith(".mp4"))
        if files:
            n = min(N_UPLOAD_SAMPLES, len(files))
            picks = [files[i * (len(files) - 1) // max(n - 1, 1)] for i in range(n)]
            assets.extend(os.path.join(UPLOADS_DIR, f) for f in picks)
    return assets


def run_with_assets(force_kind: str | None, assets: list[str]) -> list[dict]:
    """Wrap verify_pipeline._run_with_kind but with a custom asset list.

    _run_with_kind hardcodes a 3-asset list; we monkey-patch _pick_sample_videos
    so it returns our wider set without forking the rename-and-reload logic.
    """
    import verify_pipeline as vp
    orig = vp._pick_sample_videos
    vp._pick_sample_videos = lambda n_uploads=2: assets
    try:
        results, kind = _run_with_kind(force_kind)
    finally:
        vp._pick_sample_videos = orig
    return results


def render_markdown(full_results: list[dict], so_results: list[dict]) -> str:
    """Side-by-side markdown table for the thesis."""
    out = []
    out.append("# eval_heldout — FusionModel vs ScoreOnlyFusion\n")
    out.append(f"_generated {time.strftime('%Y-%m-%d %H:%M:%S')}_\n\n")
    out.append("| video | so verdict | so fake_p | full verdict | full fake_p | Δseverity |")
    out.append("|---|---|---:|---|---:|---:|")
    for so, full in zip(so_results, full_results):
        v = so["__video"]
        so_v, so_p = so.get("verdict", "?"), so.get("fake_probability", 0.0)
        fu_v, fu_p = full.get("verdict", "?"), full.get("fake_probability", 0.0)
        d_sev = VERDICT_SEVERITY.get(fu_v, -1) - VERDICT_SEVERITY.get(so_v, -1)
        out.append(f"| `{v}` | {so_v} | {so_p:.1f} | {fu_v} | {fu_p:.1f} | {d_sev:+d} |")
    return "\n".join(out)


def main():
    assets = pick_assets()
    print(f"Evaluating {len(assets)} assets:")
    for a in assets:
        print(f"  {a}")
    print()

    # We need a FusionModel checkpoint to compare. If only ScoreOnlyFusion is
    # present (e.g. after a successful rollback), there's nothing to compare —
    # report and exit.
    if not os.path.exists(PRIMARY_WEIGHTS):
        print(f"No checkpoint at {PRIMARY_WEIGHTS}; cannot evaluate.")
        return 1
    if not os.path.exists(BACKUP_WEIGHTS):
        print(f"No backup at {BACKUP_WEIGHTS}; cannot probe ScoreOnlyFusion.")
        print("Run scripts/train_fusion.py first to seed the .bak files.")
        return 1

    print("=== ScoreOnlyFusion (forced via .bak) ===")
    so_results = run_with_assets("score_only", assets)
    print()

    print("=== FusionModel (whatever's at best.pt right now) ===")
    full_results = run_with_assets(None, assets)
    print()

    md = render_markdown(full_results, so_results)
    print(md)

    # JSON sidecar so the thesis can pull per-branch numbers verbatim.
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(REPO_ROOT, "outputs")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, f"eval_heldout_{ts}.json")
    with open(json_path, "w") as f:
        json.dump({
            "timestamp": ts,
            "assets": [os.path.basename(a) for a in assets],
            "scoreonly": so_results,
            "fusion": full_results,
        }, f, indent=2, default=str)
    print(f"\nJSON sidecar: {json_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
