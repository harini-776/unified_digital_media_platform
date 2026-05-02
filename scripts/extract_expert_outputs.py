"""
Extract per-video expert outputs (scores + embeddings + labels) for fusion training.

Walks services/api/uploads/ + the known fake at deepfake_test_video.mp4, runs
each through the production pipeline (with HF backends if env vars set), and
dumps per-video .npz files at data/cache/fusion/<hash>.npz with:

    scores      (5,)   face/lipsync/voice/blink/headmotion (0-100, normalized to [0,1])
    face_emb    (D_f,) from face_detector embedding (None → zeros)
    voice_emb   (D_v,)
    lipsync_emb (D_l,)
    label       ()     0=real, 1=fake
    is_synth    ()     bool — True if synthetic perturbation
    split       ()     'train' / 'val' / 'test'

Labeling (A-1.c):
  - deepfake_test_video.mp4 → label=1 (real fake), forced into train split
    so the model has at least one real positive to learn from
  - All services/api/uploads/*.mp4 → label=0 (real)
  - For each real, generate one audio-perturbed synthetic positive
    (label=1, is_synth=True) — perturbed audio drives HF voice toward
    "fake" while HF face stays "real", teaching fusion that high voice +
    low face = fake. Complements the known fake (mid face, high voice).

Run:
    FACE_BACKEND=hf VOICE_BACKEND=hf \\
      python scripts/extract_expert_outputs.py [--force] [--limit N]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "services/api"))
sys.path.insert(0, REPO_ROOT)
os.chdir(os.path.join(REPO_ROOT, "services/api"))

from app.services.ai.pipeline import run_analysis  # noqa: E402

UPLOADS_DIR = os.path.join(REPO_ROOT, "services/api/uploads")
KNOWN_FAKE = os.path.join(REPO_ROOT, "deepfake_test_video.mp4")
CACHE_DIR = os.path.join(REPO_ROOT, "data/cache/fusion")
DIMS_FILE = os.path.join(REPO_ROOT, "data/cache/dims.json")

# Synthetic audio-positive count cap (don't perturb every real — keeps the
# fusion training set roughly 1:1 between fake-style and real-style samples
# without over-weighting one perturbation kernel)
SYNTH_AUDIO_FRACTION = 0.30   # perturb ~30% of reals into audio-fake counterparts


def deterministic_split(filename: str, train_pct: float = 0.70, val_pct: float = 0.15) -> str:
    h = int(hashlib.md5(filename.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    if h < train_pct:
        return "train"
    if h < train_pct + val_pct:
        return "val"
    return "test"


def cache_key(video_path: str, suffix: str = "") -> str:
    h = hashlib.md5((video_path + suffix).encode()).hexdigest()[:12]
    return f"fusion_{h}.npz"


def _run_ffmpeg(cmd: list[str], output_video: str) -> bool:
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return result.returncode == 0 and os.path.exists(output_video) and os.path.getsize(output_video) > 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def perturb_audio_inplace(input_video: str, output_video: str) -> bool:
    """Audio-only degradation (B-3 baseline kernel)."""
    cmd = [
        "ffmpeg", "-y", "-i", input_video,
        "-c:v", "copy",
        "-af", "aresample=8000,aresample=16000,acompressor=threshold=-20dB:ratio=8",
        "-c:a", "aac", "-b:a", "16k",
        output_video,
    ]
    return _run_ffmpeg(cmd, output_video)


def perturb_video_compression(input_video: str, output_video: str) -> bool:
    """Video-only heavy H.264 compression. Stresses the face branch — clean
    audio passthrough means voice score should stay near real."""
    cmd = [
        "ffmpeg", "-y", "-i", input_video,
        "-c:v", "libx264", "-crf", "38", "-preset", "ultrafast",
        "-c:a", "copy",
        output_video,
    ]
    return _run_ffmpeg(cmd, output_video)


def perturb_joint_av(input_video: str, output_video: str) -> bool:
    """Joint audio + video degradation. Stresses both branches."""
    cmd = [
        "ffmpeg", "-y", "-i", input_video,
        "-c:v", "libx264", "-crf", "35", "-preset", "ultrafast",
        "-af", "aresample=8000,aresample=16000",
        "-c:a", "aac", "-b:a", "24k",
        output_video,
    ]
    return _run_ffmpeg(cmd, output_video)


def perturb_pitch_shift(input_video: str, output_video: str) -> bool:
    """Voice-only: ~+1 semitone shift via asetrate trick + light denoise.
    Different signature from perturb_audio_inplace's bandwidth degradation —
    distinct generator-style artifact."""
    # asetrate=16000*1.06 ≈ +1 semitone (2^(1/12) ≈ 1.0595). Then resample to
    # restore the playback rate, so duration is preserved and pitch is shifted.
    cmd = [
        "ffmpeg", "-y", "-i", input_video,
        "-c:v", "copy",
        "-af", "asetrate=16000*1.06,aresample=16000,afftdn=nf=-25",
        "-c:a", "aac", "-b:a", "96k",
        output_video,
    ]
    return _run_ffmpeg(cmd, output_video)


# Ordered list — kernel selection uses (hash mod len) so the order is the
# enum. Don't reorder or insert in the middle without also bumping a cache
# version, otherwise existing npz files become stale.
_PERTURBATION_KERNELS = [
    ("audio_bandlimit", perturb_audio_inplace),
    ("video_compression", perturb_video_compression),
    ("joint_av", perturb_joint_av),
    ("pitch_shift", perturb_pitch_shift),
]


def select_kernel(filename: str) -> tuple[str, callable]:
    """Deterministic per-filename kernel choice. Same file → same kernel
    across runs, so re-extracting with --force is reproducible."""
    h = int(hashlib.md5((filename + "_kernel").encode()).hexdigest()[:8], 16)
    return _PERTURBATION_KERNELS[h % len(_PERTURBATION_KERNELS)]


def get_dims() -> dict[str, int]:
    import json
    with open(DIMS_FILE) as f:
        d = json.load(f)
    return {"face": int(d["face"]), "voice": int(d["voice"]), "lipsync": int(d["lipsync"])}


def harvest_one(video_path: str, label: int, is_synth: bool, split: str,
                dims: dict[str, int], cache_path: str) -> dict | None:
    """Run pipeline on one video, write .npz, return summary dict (or None on failure)."""
    try:
        result = run_analysis(video_path)
    except Exception as exc:
        print(f"  ERROR pipeline failed: {type(exc).__name__}: {exc}")
        return None

    # Convert per-branch scores to [0,1] vector in canonical order
    score_vec = np.array([
        float(result.get("face_score", 50.0)) / 100.0,
        float(result.get("lipsync_score", 50.0)) / 100.0,
        float(result.get("voice_score", 50.0)) / 100.0,
        float(result.get("blink_score", 50.0)) / 100.0,
        float(result.get("headmotion_score", 50.0)) / 100.0,
    ], dtype=np.float32)

    # Embeddings — None when analyzer fell back to heuristic with no embedding.
    # Substitute zeros at the configured dim so downstream training has stable
    # tensor shapes; FusionModel's ModalityGate handles zero embeddings cleanly.
    def emb_or_zero(branch: str, dim: int) -> np.ndarray:
        # The pipeline's result dict doesn't surface embeddings. Re-extract by
        # calling analyzers individually — but that doubles the cost. Instead,
        # we monkeypatch run_analysis to capture them. See harvest_one_with_embs.
        return np.zeros(dim, dtype=np.float32)

    # The pipeline doesn't surface embeddings in its result dict. We need the
    # raw analyzer outputs. Patch by calling pipeline differently — handled in
    # the alternate path below. For now just save scores + zero-embeddings.
    # (This branch is unused; harvest_one_with_embs is the real harvester.)
    raise NotImplementedError("Use harvest_one_with_embs — pipeline.run_analysis doesn't return embeddings")


def harvest_one_with_embs(video_path: str, label: int, is_synth: bool, split: str,
                          dims: dict[str, int], cache_path: str) -> dict | None:
    """
    Re-runs the per-branch analyzers individually so we can capture each
    branch's embedding. Same code paths as pipeline.run_analysis, but plumbed
    so embeddings survive into the cache file.
    """
    from app.services.ai.extractor import extract_frames, extract_audio
    from app.services.ai.face_detector import analyze_faces
    from app.services.ai.voice_analyzer import analyze_voice
    from app.services.ai.lipsync_analyzer import analyze_lipsync
    from app.services.ai.blink_detector import analyze_blinks
    from app.services.ai.headmotion_analyzer import analyze_headmotion

    with tempfile.TemporaryDirectory() as workdir:
        try:
            frames = extract_frames(video_path, workdir, fps=2, max_frames=60)
            audio = extract_audio(video_path, workdir)
        except Exception as exc:
            print(f"  ERROR extraction failed: {type(exc).__name__}: {exc}")
            return None

        if not frames or len(frames) < 10:
            n = len(frames) if frames else 0
            print(f"  ERROR: too few frames ({n}); skipping (need >=10)")
            return None

        try:
            face_r = analyze_faces(frames)
            voice_r = analyze_voice(audio)
            lipsync_r = analyze_lipsync(frames, audio)
            blink_r = analyze_blinks(frames)
            headmotion_r = analyze_headmotion(frames)
        except Exception as exc:
            print(f"  ERROR analyzer failed: {type(exc).__name__}: {exc}")
            return None

    score_vec = np.array([
        float(face_r.get("face_score", 50.0)) / 100.0,
        float(lipsync_r.get("lipsync_score", 50.0)) / 100.0,
        float(voice_r.get("voice_score", 50.0)) / 100.0,
        float(blink_r.get("blink_score", 50.0)) / 100.0,
        float(headmotion_r.get("headmotion_score", 50.0)) / 100.0,
    ], dtype=np.float32)

    def coerce(emb, dim: int) -> tuple[np.ndarray, bool]:
        """Returns (embedding-of-correct-dim, valid?). Valid means: analyzer
        returned a non-None, non-all-zero embedding (i.e. a real signal, not
        the heuristic-fallback zero vector)."""
        if emb is None:
            return np.zeros(dim, dtype=np.float32), False
        arr = np.asarray(emb, dtype=np.float32).reshape(-1)
        if arr.shape[0] != dim:
            print(f"  WARN: embedding dim mismatch (got {arr.shape[0]}, expected {dim}); padding/truncating")
            if arr.shape[0] < dim:
                arr = np.concatenate([arr, np.zeros(dim - arr.shape[0], dtype=np.float32)])
            else:
                arr = arr[:dim]
        valid = bool(np.any(arr != 0.0))
        return arr, valid

    face_emb, face_emb_valid = coerce(face_r.get("embedding"), dims["face"])
    voice_emb, voice_emb_valid = coerce(voice_r.get("embedding"), dims["voice"])
    lipsync_emb, lipsync_emb_valid = coerce(lipsync_r.get("embedding"), dims["lipsync"])

    np.savez_compressed(
        cache_path,
        scores=score_vec,
        face_emb=face_emb,
        voice_emb=voice_emb,
        lipsync_emb=lipsync_emb,
        label=np.int8(label),
        is_synth=np.bool_(is_synth),
        split=split,
        face_method=face_r.get("details", {}).get("method", ""),
        voice_method=voice_r.get("details", {}).get("method", ""),
        face_emb_valid=np.bool_(face_emb_valid),
        voice_emb_valid=np.bool_(voice_emb_valid),
        lipsync_emb_valid=np.bool_(lipsync_emb_valid),
    )
    return {
        "scores": score_vec.tolist(),
        "label": label,
        "split": split,
        "is_synth": is_synth,
        "face_method": face_r.get("details", {}).get("method", ""),
        "voice_method": voice_r.get("details", {}).get("method", ""),
        "face_emb_valid": face_emb_valid,
        "voice_emb_valid": voice_emb_valid,
        "lipsync_emb_valid": lipsync_emb_valid,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Delete data/cache/fusion/ before extracting (mandatory after backend changes)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N real uploads (for quick testing)")
    parser.add_argument("--no-synth", action="store_true",
                        help="Skip synthetic audio-perturbed positives")
    args = parser.parse_args()

    if not os.environ.get("FACE_BACKEND") and not os.environ.get("VOICE_BACKEND"):
        print("WARN: FACE_BACKEND/VOICE_BACKEND not set — extracting heuristic embeddings")
        print("      Set FACE_BACKEND=hf VOICE_BACKEND=hf for the HF embeddings the FusionModel was wired for")

    if args.force and os.path.exists(CACHE_DIR):
        print(f"--force: removing {CACHE_DIR}")
        shutil.rmtree(CACHE_DIR)
    os.makedirs(CACHE_DIR, exist_ok=True)

    dims = get_dims()
    print(f"Embedding dims: {dims}")
    print(f"Backends: FACE={os.environ.get('FACE_BACKEND','default')} VOICE={os.environ.get('VOICE_BACKEND','default')}")

    # ── Build worklist ──────────────────────────────────────────
    uploads = sorted(f for f in os.listdir(UPLOADS_DIR) if f.lower().endswith(".mp4"))
    if args.limit:
        uploads = uploads[:args.limit]

    # Worklist tuple: (path, label, is_synth, split, key_suffix, kernel_name)
    # kernel_name is "" for non-synth entries.
    worklist: list[tuple[str, int, bool, str, str, str]] = []

    # The known fake: forced into 'train' so fusion has a real positive to learn from
    worklist.append((KNOWN_FAKE, 1, False, "train", "", ""))

    # All real uploads
    for fname in uploads:
        worklist.append((os.path.join(UPLOADS_DIR, fname), 0, False, deterministic_split(fname), "", ""))

    # Synthetic positives — pick a deterministic subset of reals; each gets ONE
    # of the four kernels chosen by filename hash. B-4a: this replaces B-3's
    # single-kernel signature with 4-way diversity, so the model can't memorize
    # "this perturbation = fake" without learning generalizable features.
    if not args.no_synth:
        synth_reals = [f for f in uploads
                       if (int(hashlib.md5(f.encode()).hexdigest()[8:16], 16) / 0xFFFFFFFF) < SYNTH_AUDIO_FRACTION]
        kernel_counts: dict[str, int] = {name: 0 for name, _ in _PERTURBATION_KERNELS}
        for fname in synth_reals:
            kernel_name, _ = select_kernel(fname)
            kernel_counts[kernel_name] += 1
            # Cache suffix encodes the kernel name so re-runs with a different
            # kernel set don't collide with stale npz files.
            suffix = f"_synth_{kernel_name}"
            worklist.append((os.path.join(UPLOADS_DIR, fname), 1, True,
                             deterministic_split(fname), suffix, kernel_name))
        print(f"Will generate {len(synth_reals)} synthetic positives "
              f"({SYNTH_AUDIO_FRACTION:.0%} of reals), kernel mix: {kernel_counts}")

    print(f"\nTotal worklist: {len(worklist)} samples")
    splits = {"train": 0, "val": 0, "test": 0}
    for _, _, _, split, _, _ in worklist:
        splits[split] += 1
    print(f"  per split: {splits}")
    pos = sum(1 for _, lbl, _, _, _, _ in worklist if lbl == 1)
    print(f"  positives (fake): {pos}, negatives (real): {len(worklist) - pos}")

    # Map kernel names back to functions for dispatch.
    kernel_fn_by_name = {name: fn for name, fn in _PERTURBATION_KERNELS}

    # ── Process each ────────────────────────────────────────────
    n_done = 0
    n_skip = 0
    n_fail = 0
    # Embedding-validity tallies: how often did each branch return a real
    # (non-fallback) embedding? Reported per-class so we can spot e.g. face
    # detector failing more on positives than negatives.
    valid_counts = {"pos": {"face": 0, "voice": 0, "lipsync": 0, "total": 0},
                    "neg": {"face": 0, "voice": 0, "lipsync": 0, "total": 0}}
    t0 = time.time()
    synth_workdir = tempfile.mkdtemp(prefix="extract_synth_")
    try:
        for idx, (vpath, label, is_synth, split, key_suffix, kernel_name) in enumerate(worklist, 1):
            cache_path = os.path.join(CACHE_DIR, cache_key(vpath, key_suffix))
            if os.path.exists(cache_path):
                n_skip += 1
                continue

            elapsed = time.time() - t0
            eta_s = (elapsed / max(n_done, 1)) * (len(worklist) - n_done) if n_done > 0 else 0
            tag = f"(synth:{kernel_name})" if is_synth else ""
            print(f"[{idx}/{len(worklist)}] {os.path.basename(vpath)}{tag} "
                  f"label={label} split={split} (elapsed {elapsed/60:.1f}m, eta {eta_s/60:.1f}m)")

            actual_path = vpath
            if is_synth:
                synth_path = os.path.join(synth_workdir, f"{idx}_{kernel_name}.mp4")
                kernel_fn = kernel_fn_by_name[kernel_name]
                if not kernel_fn(vpath, synth_path):
                    print(f"  WARN: perturbation '{kernel_name}' failed; skipping")
                    n_fail += 1
                    continue
                actual_path = synth_path

            summary = harvest_one_with_embs(actual_path, label, is_synth, split, dims, cache_path)
            if summary is None:
                n_fail += 1
            else:
                n_done += 1
                bucket = "pos" if label == 1 else "neg"
                valid_counts[bucket]["total"] += 1
                if summary.get("face_emb_valid"):
                    valid_counts[bucket]["face"] += 1
                if summary.get("voice_emb_valid"):
                    valid_counts[bucket]["voice"] += 1
                if summary.get("lipsync_emb_valid"):
                    valid_counts[bucket]["lipsync"] += 1
                # Light progress: print scores for the known fake + first few uploads so the user sees signal
                if idx <= 3 or vpath == KNOWN_FAKE or is_synth:
                    s = summary["scores"]
                    print(f"  scores [face,lipsync,voice,blink,head]: "
                          f"[{s[0]:.2f} {s[1]:.2f} {s[2]:.2f} {s[3]:.2f} {s[4]:.2f}]  "
                          f"face_method={summary['face_method']} voice_method={summary['voice_method']}")
    finally:
        shutil.rmtree(synth_workdir, ignore_errors=True)

    print(f"\n=== done ===")
    print(f"  cached: {n_done}, skipped (already cached): {n_skip}, failed: {n_fail}")
    print(f"  total time: {(time.time() - t0) / 60:.1f}m")
    print(f"  cache dir: {CACHE_DIR}")

    # ── Embedding-validity report ────────────────────────────────
    # train_fusion.py gates on face + voice embedding validity. Lipsync is
    # informational only — weights/lipsync/best.pt was never trained, so the
    # lipsync analyzer always falls back to its heuristic (embedding=None).
    # An expected 0% lipsync validity is the deployment reality, not a bug.
    GATED_BRANCHES = {"face", "voice"}
    print("\n=== embedding validity ===")
    for bucket in ("pos", "neg"):
        c = valid_counts[bucket]
        n = c["total"]
        if n == 0:
            continue
        label_name = "positives (fake)" if bucket == "pos" else "negatives (real)"
        print(f"  {label_name} (n={n}):")
        for branch in ("face", "voice", "lipsync"):
            v = c[branch]
            pct = (v / n) * 100.0
            if branch == "lipsync":
                flag = "  (heuristic-only — no trained weights)"
            elif branch in GATED_BRANCHES and pct < 80 and bucket == "pos":
                flag = " *LOW — train_fusion will refuse*"
            else:
                flag = ""
            print(f"    {branch}_emb_valid: {v}/{n} ({pct:.0f}%){flag}")


if __name__ == "__main__":
    main()
