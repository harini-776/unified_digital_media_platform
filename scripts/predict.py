"""
Standalone Inference Script — Multimodal Deepfake Detection.

Usage:
    python scripts/predict.py --video path/to/video.mp4

Output (JSON):
    {
      "final_label": "AUTHENTIC" | "MANIPULATED",
      "fake_probability": 0-100,
      "per_signal_scores": {
        "face_score": ..., "lipsync_score": ..., "voice_score": ...,
        "blink_score": ..., "headmotion_score": ...
      },
      "explanation": "lip-sync mismatch high, blink abnormal",
      "confidence_calibrated_probability": 0-100,
      "uncertainty_flag": "LOW" | "MEDIUM" | "HIGH",
      "entropy": ...,
      "modality_weights": {...},
      "fusion_method": "..."
    }
"""
from __future__ import annotations
import argparse, os, sys, json, shutil, uuid, tempfile

# Add project root to path
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Add services/api to path for app imports
API_ROOT = os.path.join(PROJECT_ROOT, "services", "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)


def run_predict(video_path: str, output_json: str | None = None, verbose: bool = False) -> dict:
    """
    Run complete deepfake detection pipeline on a video file.

    Args:
        video_path: Path to .mp4/.mov/.avi file
        output_json: Optional path to save JSON output
        verbose: Print progress to stdout

    Returns:
        Result dict with all detection fields
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    ext = os.path.splitext(video_path)[1].lower()
    if ext not in {".mp4", ".mov", ".avi", ".webm", ".mkv"}:
        raise ValueError(f"Unsupported video format: {ext}")

    def progress(stage, pct):
        if verbose:
            print(f"  [{pct:3d}%] {stage}", flush=True)

    if verbose:
        print(f"\nAnalyzing: {video_path}")
        print("-" * 50)

    # Import pipeline (lazy to avoid slow startup)
    from app.services.ai.extractor import extract_frames, extract_audio, get_video_metadata
    from app.services.ai.face_detector import analyze_faces
    from app.services.ai.voice_analyzer import analyze_voice
    from app.services.ai.lipsync_analyzer import analyze_lipsync
    from app.services.ai.blink_detector import analyze_blinks
    from app.services.ai.headmotion_analyzer import analyze_headmotion
    from app.services.ai.fusion import weighted_fusion

    work_dir   = os.path.join(tempfile.gettempdir(), "deepfake_predict", uuid.uuid4().hex)
    frames_dir = os.path.join(work_dir, "frames")
    audio_dir  = os.path.join(work_dir, "audio")

    try:
        progress("extracting metadata", 5)
        metadata = get_video_metadata(video_path)

        progress("extracting frames", 10)
        frames = extract_frames(video_path, frames_dir, fps=10, max_frames=90)

        progress("extracting audio", 20)
        audio_path = extract_audio(video_path, audio_dir)

        if verbose:
            print(f"  Frames: {len(frames)}, Audio: {'yes' if audio_path else 'no'}")
            print(f"  Duration: {metadata.get('duration_seconds', 0):.1f}s  "
                  f"FPS: {metadata.get('fps', 0):.1f}  "
                  f"Resolution: {metadata.get('width',0)}x{metadata.get('height',0)}")

        progress("face analysis", 30)
        face_result = analyze_faces(frames)

        progress("voice analysis", 45)
        voice_result = analyze_voice(audio_path)

        progress("lip-sync analysis", 58)
        lipsync_result = analyze_lipsync(frames, audio_path)

        progress("blink analysis", 72)
        blink_result = analyze_blinks(frames)

        progress("head motion analysis", 82)
        headmotion_result = analyze_headmotion(frames)

        progress("fusion + calibration", 92)
        fusion_result = weighted_fusion(
            face_score=face_result["face_score"],
            voice_score=voice_result["voice_score"],
            lipsync_score=lipsync_result["lipsync_score"],
            blink_score=blink_result["blink_score"],
            headmotion_score=headmotion_result["headmotion_score"],
            face_embedding=face_result.get("embedding"),
            voice_embedding=voice_result.get("embedding"),
            lipsync_embedding=lipsync_result.get("embedding"),
        )

        progress("done", 100)

        # ── Build result ──────────────────────────────────────────
        verdict = fusion_result["verdict"].upper()
        # Map SUSPICIOUS -> MANIPULATED for binary output
        final_label = "MANIPULATED" if verdict in {"MANIPULATED", "SUSPICIOUS"} else "AUTHENTIC"

        result = {
            "final_label": final_label,
            "verdict": verdict,
            "fake_probability": fusion_result["fake_probability"],
            "trust_score": fusion_result["trust_score"],
            "per_signal_scores": {
                "face_score":       face_result["face_score"],
                "lipsync_score":    lipsync_result["lipsync_score"],
                "voice_score":      voice_result["voice_score"],
                "blink_score":      blink_result["blink_score"],
                "headmotion_score": headmotion_result["headmotion_score"],
            },
            "explanation":                     fusion_result.get("explanation", ""),
            "confidence_calibrated_probability": fusion_result.get("confidence_calibrated_probability"),
            "uncertainty_flag":                fusion_result.get("uncertainty_flag", "MEDIUM"),
            "entropy":                         fusion_result.get("entropy"),
            "confidence":                      fusion_result["confidence"],
            "modality_weights":                fusion_result.get("modality_weights", {}),
            "fusion_method":                   fusion_result.get("fusion_method", ""),
            "signal_details": {
                "face":       face_result.get("details", {}),
                "voice":      voice_result.get("details", {}),
                "lipsync":    lipsync_result.get("details", {}),
                "blink":      blink_result.get("details", {}),
                "headmotion": headmotion_result.get("details", {}),
                "video_metadata": metadata,
            },
        }

        if verbose:
            print("\n" + "=" * 50)
            print(f"  VERDICT:     {result['final_label']}")
            print(f"  Fake prob:   {result['fake_probability']:.1f}%")
            print(f"  Calibrated:  {result['confidence_calibrated_probability']:.1f}%")
            print(f"  Confidence:  {result['confidence']:.3f}")
            print(f"  Uncertainty: {result['uncertainty_flag']}")
            print(f"  Explanation: {result['explanation']}")
            print("\n  Per-signal scores:")
            for k, v in result["per_signal_scores"].items():
                bar = "█" * int(v/5) + "░" * (20 - int(v/5))
                print(f"    {k:<20} {v:5.1f}%  [{bar}]")
            print("=" * 50)

        if output_json:
            os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
            with open(output_json, "w") as f:
                json.dump(result, f, indent=2, default=str)
            if verbose:
                print(f"\n  Saved to: {output_json}")

        return result

    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Multimodal Deepfake Detection — Standalone Inference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--video",  type=str, required=True, help="Path to video file")
    parser.add_argument("--output", type=str, default=None,  help="Save JSON result to path")
    parser.add_argument("--quiet",  action="store_true",     help="Suppress progress output")
    args = parser.parse_args()

    result = run_predict(
        video_path=args.video,
        output_json=args.output,
        verbose=not args.quiet,
    )

    if args.quiet:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
