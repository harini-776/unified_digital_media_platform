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


def perturb_audio_inplace(input_video: str, output_video: str) -> bool:
    """
    Re-encode video with audio degradation that mimics vocoder/synthesis artifacts:
      - Resample audio to 8kHz then back to 16kHz (loses high frequencies)
      - Re-encode at very low bitrate (16 kbit/s)
      - Add band-limited noise floor

    Video stream is copy-passthrough — only audio changes. This keeps face
    branch outputs identical (clean frames) and pushes voice branch toward fake.
    Returns True on success.
    """
    # Use ffmpeg directly. afftdn-style noise + bandlimit + heavy compression.
    cmd = [
        "ffmpeg", "-y", "-i", input_video,
        "-c:v", "copy",
        "-af", "aresample=8000,aresample=16000,acompressor=threshold=-20dB:ratio=8",
        "-c:a", "aac", "-b:a", "16k",
        output_video,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        return result.returncode == 0 and os.path.exists(output_video) and os.path.getsize(output_video) > 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


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

        if not frames:
            print(f"  ERROR: no frames extracted")
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

    def coerce(emb, dim: int) -> np.ndarray:
        if emb is None:
            return np.zeros(dim, dtype=np.float32)
        arr = np.asarray(emb, dtype=np.float32).reshape(-1)
        if arr.shape[0] != dim:
            # Embedding shape mismatch — pad or truncate. Should not happen if
            # dims.json is correct for the active backends; warn but proceed.
            print(f"  WARN: embedding dim mismatch (got {arr.shape[0]}, expected {dim}); padding/truncating")
            if arr.shape[0] < dim:
                arr = np.concatenate([arr, np.zeros(dim - arr.shape[0], dtype=np.float32)])
            else:
                arr = arr[:dim]
        return arr

    face_emb = coerce(face_r.get("embedding"), dims["face"])
    voice_emb = coerce(voice_r.get("embedding"), dims["voice"])
    lipsync_emb = coerce(lipsync_r.get("embedding"), dims["lipsync"])

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
    )
    return {
        "scores": score_vec.tolist(),
        "label": label,
        "split": split,
        "is_synth": is_synth,
        "face_method": face_r.get("details", {}).get("method", ""),
        "voice_method": voice_r.get("details", {}).get("method", ""),
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

    worklist: list[tuple[str, int, bool, str, str]] = []   # (path, label, is_synth, split, key_suffix)

    # The known fake: forced into 'train' so fusion has a real positive to learn from
    worklist.append((KNOWN_FAKE, 1, False, "train", ""))

    # All real uploads
    for fname in uploads:
        worklist.append((os.path.join(UPLOADS_DIR, fname), 0, False, deterministic_split(fname), ""))

    # Synthetic audio-perturbed positives — perturb a deterministic subset of reals
    if not args.no_synth:
        # Pick reals with hash mod < SYNTH_AUDIO_FRACTION (deterministic, reproducible)
        synth_reals = [f for f in uploads
                       if (int(hashlib.md5(f.encode()).hexdigest()[8:16], 16) / 0xFFFFFFFF) < SYNTH_AUDIO_FRACTION]
        print(f"Will generate {len(synth_reals)} synthetic audio-fake positives "
              f"({SYNTH_AUDIO_FRACTION:.0%} of reals)")
        for fname in synth_reals:
            worklist.append((os.path.join(UPLOADS_DIR, fname), 1, True, deterministic_split(fname), "_audiofake"))

    print(f"\nTotal worklist: {len(worklist)} samples")
    splits = {"train": 0, "val": 0, "test": 0}
    for _, _, _, split, _ in worklist:
        splits[split] += 1
    print(f"  per split: {splits}")
    pos = sum(1 for _, lbl, _, _, _ in worklist if lbl == 1)
    print(f"  positives (fake): {pos}, negatives (real): {len(worklist) - pos}")

    # ── Process each ────────────────────────────────────────────
    n_done = 0
    n_skip = 0
    n_fail = 0
    t0 = time.time()
    synth_workdir = tempfile.mkdtemp(prefix="extract_synth_")
    try:
        for idx, (vpath, label, is_synth, split, key_suffix) in enumerate(worklist, 1):
            cache_path = os.path.join(CACHE_DIR, cache_key(vpath, key_suffix))
            if os.path.exists(cache_path):
                n_skip += 1
                continue

            elapsed = time.time() - t0
            eta_s = (elapsed / max(n_done, 1)) * (len(worklist) - n_done) if n_done > 0 else 0
            print(f"[{idx}/{len(worklist)}] {os.path.basename(vpath)}{'(synth-audio)' if is_synth else ''} "
                  f"label={label} split={split} (elapsed {elapsed/60:.1f}m, eta {eta_s/60:.1f}m)")

            actual_path = vpath
            if is_synth:
                # Generate audio-perturbed copy in a temp file
                synth_path = os.path.join(synth_workdir, f"{idx}_audiofake.mp4")
                if not perturb_audio_inplace(vpath, synth_path):
                    print(f"  WARN: audio perturbation failed; skipping")
                    n_fail += 1
                    continue
                actual_path = synth_path

            summary = harvest_one_with_embs(actual_path, label, is_synth, split, dims, cache_path)
            if summary is None:
                n_fail += 1
            else:
                n_done += 1
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


if __name__ == "__main__":
    main()
