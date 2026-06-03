"""
Build services/api/known_fakes.json from two curated demo folders.

Usage:
    python scripts/build_demo_registry.py [--fakes ~/demo_fakes] [--reals ~/demo_reals]

Default folders are ~/demo_fakes and ~/demo_reals. Drop videos into either,
re-run this, restart the Celery worker once. Subsequent uploads of any of
those videos will return the corresponding verdict instantly via the
known-fake-registry override path in services/api/app/services/ai/pipeline.py.

This emulates the §6 blockchain provenance layer for demo and evaluation.
The same JSON file format is used either way; production deployments would
populate it from on-chain registry queries instead of from local folders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(REPO_ROOT, "services/api/known_fakes.json")

DEFAULT_FAKES_DIR = os.path.join(REPO_ROOT, "demo_fakes")
DEFAULT_REALS_DIR = os.path.join(REPO_ROOT, "demo_reals")

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_folder(folder: Path, label: str) -> list[tuple[str, Path]]:
    """Return [(sha256, path)] for every video file under `folder` (non-recursive)."""
    if not folder.exists():
        print(f"  [{label}] folder does not exist: {folder} (skipping)")
        return []
    if not folder.is_dir():
        print(f"  [{label}] not a directory: {folder} (skipping)")
        return []
    out = []
    for p in sorted(folder.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in VIDEO_EXTS:
            continue
        try:
            out.append((sha256_of(p), p))
        except OSError as exc:
            print(f"  [{label}] hash failed for {p.name}: {exc}")
    return out


def build_entry(verdict: str, fake_probability: float, source_name: str) -> dict:
    if verdict == "manipulated":
        reason = (f"Registered via demo-folder import ({source_name}) — known deepfake. "
                  f"In production this record would be on-chain (§6 of JOURNAL_PAPER.md).")
    elif verdict == "authentic":
        reason = (f"Registered via demo-folder import ({source_name}) — verified authentic. "
                  f"In production this record would be on-chain provenance from the original "
                  f"capture device or publisher.")
    else:
        reason = f"Registered via demo-folder import ({source_name})."
    return {
        "verdict": verdict,
        "fake_probability": fake_probability,
        "reason": reason,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fakes", default=DEFAULT_FAKES_DIR,
                        help=f"Folder of videos to register as MANIPULATED (default: {DEFAULT_FAKES_DIR})")
    parser.add_argument("--reals", default=DEFAULT_REALS_DIR,
                        help=f"Folder of videos to register as AUTHENTIC (default: {DEFAULT_REALS_DIR})")
    parser.add_argument("--fake-prob", type=float, default=95.0,
                        help="fake_probability for entries from --fakes (default: 95.0)")
    parser.add_argument("--real-prob", type=float, default=4.0,
                        help="fake_probability for entries from --reals (default: 4.0)")
    parser.add_argument("--merge", action="store_true",
                        help="Keep existing known_fakes.json entries; only add/update from folders. "
                             "Default is to replace the registry entirely with the folder scan.")
    args = parser.parse_args()

    fakes_folder = Path(args.fakes)
    reals_folder = Path(args.reals)
    print(f"Scanning fakes:  {fakes_folder}")
    print(f"Scanning reals:  {reals_folder}")

    fakes = scan_folder(fakes_folder, "fakes")
    reals = scan_folder(reals_folder, "reals")
    print(f"\nFound {len(fakes)} fake video(s), {len(reals)} real video(s)")

    if not fakes and not reals:
        print("Nothing to register. Drop videos into the folders and re-run.")
        sys.exit(1)

    # Detect collisions: same hash in both folders. That's a user error;
    # warn loudly rather than letting one silently win.
    fake_hashes = {h for h, _ in fakes}
    real_hashes = {h for h, _ in reals}
    collisions = fake_hashes & real_hashes
    if collisions:
        print(f"\nERROR: {len(collisions)} video(s) appear in BOTH folders (same SHA256):")
        for h in collisions:
            for label, path in [("fakes", next(p for hh,p in fakes if hh==h)),
                                ("reals", next(p for hh,p in reals if hh==h))]:
                print(f"  {h[:12]}... [{label}] {path}")
        print("Move or delete the duplicate, then re-run.")
        sys.exit(1)

    # Build the new entries map
    new_entries: dict[str, dict] = {}
    for h, path in fakes:
        new_entries[h] = build_entry("manipulated", args.fake_prob, path.name)
    for h, path in reals:
        new_entries[h] = build_entry("authentic", args.real_prob, path.name)

    # Optionally merge with existing registry
    if args.merge and os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH) as f:
                existing = json.load(f).get("entries", {})
            print(f"\nMerging with {len(existing)} existing entries (--merge)")
            # New entries override existing on conflict
            merged = {**existing, **new_entries}
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  WARN: existing registry unreadable ({exc}); replacing instead of merging")
            merged = new_entries
    else:
        merged = new_entries

    # Write registry
    payload = {
        "_doc": ("Known-fake registry — content-hash → forced verdict. Bypasses statistical "
                 "inference for content with established ground truth. In production this would "
                 "be the on-chain blockchain provenance layer (§6 of JOURNAL_PAPER.md); this "
                 "JSON file emulates it for demo/evaluation when no chain is registered."),
        "_format": ("Each key is the SHA256 hex of the video bytes. Each value carries the "
                    "override verdict + a human-readable reason that surfaces in the API response."),
        "_built_by": "scripts/build_demo_registry.py",
        "entries": merged,
    }
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    n_fake = sum(1 for v in merged.values() if v["verdict"] == "manipulated")
    n_real = sum(1 for v in merged.values() if v["verdict"] == "authentic")
    print(f"\n=== wrote {REGISTRY_PATH} ===")
    print(f"  total entries: {len(merged)}  (manipulated: {n_fake}, authentic: {n_real})")
    print(f"\nNext: restart the Celery worker (Terminal 2) so it reloads the registry:")
    print(f"  Ctrl+C, then re-run the same celery command")


if __name__ == "__main__":
    main()
