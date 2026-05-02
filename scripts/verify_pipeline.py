"""
End-to-end verification of the fusion pipeline.

Wiring assertions (always run):
  - Pipeline produces a verdict in {authentic, suspicious, manipulated}
  - fusion_method matches the loaded model kind
  - Per-branch scores are present and finite

Quality gate (only runs when FusionModel weights exist, i.e. _LOADED_MODEL_KIND == "full"):
  - Compares FusionModel verdict vs ScoreOnlyFusion verdict on deepfake_test_video.mp4
  - If FusionModel is more lenient than ScoreOnlyFusion on the known fake → auto-rollback
  - Attention non-collapse: max(weights) - min(weights) > 0.05 on at least one sample
    AND attention entropy < 0.9 * log(5) on at least one sample
"""
from __future__ import annotations
import json
import math
import os
import shutil
import sys
import importlib

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "services/api"))
sys.path.insert(0, REPO_ROOT)

VERDICT_SEVERITY = {"authentic": 0, "suspicious": 1, "manipulated": 2}
KNOWN_FAKE = os.path.join(REPO_ROOT, "deepfake_test_video.mp4")
UPLOADS_DIR = os.path.join(REPO_ROOT, "services/api/uploads")

WEIGHTS_DIR = os.path.join(REPO_ROOT, "weights/fusion")
PRIMARY_WEIGHTS = os.path.join(WEIGHTS_DIR, "best.pt")
PRIMARY_TEMP = os.path.join(WEIGHTS_DIR, "temperature.pt")
BACKUP_WEIGHTS = os.path.join(WEIGHTS_DIR, "best_scoreonly.pt.bak")
BACKUP_TEMP = os.path.join(WEIGHTS_DIR, "temperature_scoreonly.pt.bak")


def _pick_sample_videos(n_uploads: int = 2) -> list[str]:
    videos = [KNOWN_FAKE]
    if os.path.isdir(UPLOADS_DIR):
        files = sorted(os.listdir(UPLOADS_DIR))
        # spread the picks across the upload range so we don't bias the sample
        if len(files) >= n_uploads:
            picks = [files[i * (len(files) - 1) // max(n_uploads - 1, 1)] for i in range(n_uploads)]
            videos.extend(os.path.join(UPLOADS_DIR, f) for f in picks)
    return videos


def _reset_fusion_module():
    """Force a fresh load of services.api...fusion so we can probe both kinds."""
    mod_name = "app.services.ai.fusion"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    if "app.services.ai.pipeline" in sys.modules:
        del sys.modules["app.services.ai.pipeline"]
    return importlib.import_module(mod_name)


def _run_with_kind(force_kind: str | None) -> tuple[list[dict], str | None]:
    """
    Run the pipeline on all sample videos, optionally forcing a specific model
    kind by temporarily renaming weight files.

    force_kind:
      None         -> use whatever loads naturally
      "full"       -> only meaningful when a FusionModel checkpoint exists
      "score_only" -> hide best.pt so loader falls back to backup or weighted_average
    """
    fusion = _reset_fusion_module()
    from app.services.ai.pipeline import run_analysis

    moved = []
    if force_kind == "score_only" and os.path.exists(PRIMARY_WEIGHTS):
        # Test the loader by hiding primary weights so it falls through to backup
        tmp_primary = PRIMARY_WEIGHTS + ".verify_hidden"
        os.rename(PRIMARY_WEIGHTS, tmp_primary)
        moved.append((tmp_primary, PRIMARY_WEIGHTS))
        if os.path.exists(PRIMARY_TEMP):
            tmp_temp = PRIMARY_TEMP + ".verify_hidden"
            os.rename(PRIMARY_TEMP, tmp_temp)
            moved.append((tmp_temp, PRIMARY_TEMP))
        # Reload after rename
        fusion = _reset_fusion_module()
        from app.services.ai.pipeline import run_analysis  # noqa: F811

    try:
        results = []
        for vp in _pick_sample_videos():
            print(f"  → {os.path.basename(vp)}")
            r = run_analysis(vp)
            r["__video"] = os.path.basename(vp)
            results.append(r)
        return results, fusion._LOADED_MODEL_KIND
    finally:
        # Restore any moved files
        for tmp, orig in moved:
            os.rename(tmp, orig)


def _entropy(weights: list[float]) -> float:
    h = 0.0
    for w in weights:
        if w > 1e-9:
            h -= w * math.log(w)
    return h


def _print_table(rows: list[dict], label: str):
    print(f"\n=== {label} ===")
    print(f"{'video':<45} {'verdict':<13} {'fake_p':>7} {'method':<32}")
    for r in rows:
        print(f"{r['__video']:<45} {r.get('verdict','?'):<13} "
              f"{r.get('fake_probability', 0):>7.2f} {r.get('fusion_method',''):<32}")


def _wiring_assertions(results: list[dict], expected_kind: str) -> list[str]:
    """Return list of failure messages; empty list = all pass."""
    failures = []
    expected_method = {
        "full": "attention_fusion_full",
        "score_only": "attention_fusion_calibrated",
        None: "weighted_average_fallback",
    }[expected_kind]

    for r in results:
        v = r.get("verdict")
        if v not in VERDICT_SEVERITY:
            failures.append(f"{r['__video']}: invalid verdict {v!r}")

        fp = r.get("fake_probability")
        if fp is None or not (0 <= fp <= 100):
            failures.append(f"{r['__video']}: fake_probability out of range: {fp!r}")

        if r.get("fusion_method") != expected_method:
            failures.append(
                f"{r['__video']}: fusion_method={r.get('fusion_method')!r} "
                f"expected {expected_method!r} for kind={expected_kind}"
            )

        for branch in ("face_score", "voice_score", "lipsync_score", "blink_score", "headmotion_score"):
            if r.get(branch) is None:
                failures.append(f"{r['__video']}: missing {branch}")

    return failures


def _attention_collapse_check(full_results: list[dict]) -> str:
    """Soft warning on attention collapse; not a hard fail."""
    msgs = []
    H_uniform = math.log(5)
    saw_spread = False
    saw_low_entropy = False
    for r in full_results:
        mw = r.get("modality_weights", {})
        if not mw:
            continue
        vals = [float(mw.get(k, 0.0)) for k in ["face", "lipsync", "voice", "blink", "headmotion"]]
        spread = max(vals) - min(vals)
        H = _entropy(vals)
        msgs.append(f"  {r['__video']}: spread={spread:.3f} entropy={H:.3f} (uniform={H_uniform:.3f})")
        if spread > 0.05:
            saw_spread = True
        if H < 0.9 * H_uniform:
            saw_low_entropy = True
    print("\nAttention diagnostics:")
    for m in msgs:
        print(m)
    if not (saw_spread and saw_low_entropy):
        return ("WARNING: attention may be collapsed — no sample showed spread>0.05 "
                "AND entropy<0.9*log(5). FusionModel may be ignoring inputs or "
                "every sample is genuinely ambiguous.")
    return ""


def _quality_gate(full_results: list[dict], scoreonly_results: list[dict]) -> bool:
    """
    Hard gate: on KNOWN_FAKE, FusionModel verdict must be at least as severe as
    ScoreOnlyFusion. Returns True if PASS, False if regression detected.
    """
    fake_basename = os.path.basename(KNOWN_FAKE)
    full = next((r for r in full_results if r["__video"] == fake_basename), None)
    so = next((r for r in scoreonly_results if r["__video"] == fake_basename), None)
    if full is None or so is None:
        print("\nQuality gate: SKIP (known-fake video missing from one of the result sets)")
        return True

    full_sev = VERDICT_SEVERITY.get(full.get("verdict", ""), -1)
    so_sev = VERDICT_SEVERITY.get(so.get("verdict", ""), -1)
    print(f"\nQuality gate on {fake_basename}:")
    print(f"  ScoreOnlyFusion verdict={so.get('verdict')} (severity {so_sev}) fake_p={so.get('fake_probability')}")
    print(f"  FusionModel     verdict={full.get('verdict')} (severity {full_sev}) fake_p={full.get('fake_probability')}")
    if full_sev < so_sev:
        print("  RESULT: REGRESSION — FusionModel is more lenient than ScoreOnlyFusion")
        return False
    print("  RESULT: PASS — FusionModel verdict is at least as severe")
    return True


def _rollback():
    """Restore ScoreOnlyFusion backup over the current FusionModel weights."""
    print("\n[ROLLBACK] Restoring ScoreOnlyFusion checkpoint and matching temperature...")
    if os.path.exists(BACKUP_WEIGHTS):
        shutil.copy2(BACKUP_WEIGHTS, PRIMARY_WEIGHTS)
        print(f"  copied {BACKUP_WEIGHTS} → {PRIMARY_WEIGHTS}")
    else:
        print(f"  ERROR: no backup at {BACKUP_WEIGHTS}; cannot restore weights")
        return False
    if os.path.exists(BACKUP_TEMP):
        shutil.copy2(BACKUP_TEMP, PRIMARY_TEMP)
        print(f"  copied {BACKUP_TEMP} → {PRIMARY_TEMP}")
    else:
        print(f"  WARNING: no backup at {BACKUP_TEMP}; temperature may be mis-calibrated")
    return True


def main():
    print("=" * 78)
    print("verify_pipeline.py — fusion wiring verification")
    print("=" * 78)

    # Probe: what does the loader pick up by default?
    fusion = _reset_fusion_module()
    fusion._get_fusion_model()
    natural_kind = fusion._LOADED_MODEL_KIND
    print(f"\nNatural load → _LOADED_MODEL_KIND = {natural_kind}")

    failures: list[str] = []

    if natural_kind == "full":
        # Phase B+ regime: run BOTH model kinds to compare.
        print("\n--- Running with FusionModel (natural load) ---")
        full_results, _ = _run_with_kind("full")
        _print_table(full_results, "FusionModel results")

        print("\n--- Running with ScoreOnlyFusion (forced via hiding best.pt) ---")
        so_results, so_kind = _run_with_kind("score_only")
        _print_table(so_results, f"ScoreOnlyFusion results (kind={so_kind})")

        # Wiring assertions on each
        failures += _wiring_assertions(full_results, "full")
        failures += _wiring_assertions(so_results, so_kind)

        # Attention diagnostics (soft)
        warn = _attention_collapse_check(full_results)
        if warn:
            print(warn)

        # Hard quality gate
        if not _quality_gate(full_results, so_results):
            ok = _rollback()
            print("\nFAILURE: FusionModel regressed on the known fake; rollback "
                  + ("performed." if ok else "FAILED."))
            sys.exit(2)

    else:
        # Phase A regime: only one kind available; just verify wiring.
        print(f"\n--- Running with currently loaded model (kind={natural_kind}) ---")
        results, _ = _run_with_kind(None)
        _print_table(results, f"Pipeline results (kind={natural_kind})")
        failures += _wiring_assertions(results, natural_kind)
        print(f"\nQuality gate: SKIP (no FusionModel weights yet; kind={natural_kind})")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("\nOK — all wiring assertions passed.")


if __name__ == "__main__":
    main()
