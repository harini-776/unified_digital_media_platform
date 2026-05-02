"""
Main AI Analysis Pipeline Orchestrator — Upgraded Multimodal Version.

Coordinates:
  Frame/audio extraction -> 5 expert branches -> attention fusion -> output

New capabilities:
  - 5 expert branches (adds headmotion)
  - Calibrated probability output
  - Uncertainty flag (LOW/MEDIUM/HIGH)
  - Explanation of top contributing signals
  - Per-modality weights
  - Graceful fallback for each missing modality
"""
from __future__ import annotations
import os, shutil, uuid
from app.core.config import get_settings
from app.services.ai.extractor import extract_frames, extract_audio, get_video_metadata
from app.services.ai.face_detector import analyze_faces
from app.services.ai.voice_analyzer import analyze_voice
from app.services.ai.lipsync_analyzer import analyze_lipsync
from app.services.ai.blink_detector import analyze_blinks
from app.services.ai.headmotion_analyzer import analyze_headmotion
from app.services.ai.fusion import weighted_fusion

settings = get_settings()


def run_analysis(video_path: str, progress_callback=None) -> dict:
    """
    Run the full multimodal deepfake detection pipeline.

    Args:
        video_path: Path to video file (.mp4/.mov/.avi)
        progress_callback: Optional callable(stage: str, percent: int)

    Returns:
        Complete analysis result with all output fields:
          - final_label, fake_probability, per-signal scores
          - explanation, confidence_calibrated_probability
          - uncertainty_flag, modality_weights
    """
    def cb(stage, pct):
        if progress_callback:
            progress_callback(stage, pct)

    work_dir   = os.path.join(settings.output_dir, uuid.uuid4().hex)
    frames_dir = os.path.join(work_dir, "frames")
    audio_dir  = os.path.join(work_dir, "audio")

    try:
        # ── Stage 1: Video metadata ──────────────────────────────
        cb("extracting", 5)
        metadata = get_video_metadata(video_path)

        # ── Stage 2: Frame extraction ────────────────────────────
        cb("extracting", 10)
        # Adaptive sampling: more frames = more accurate; cap at 60 for speed on CPU
        duration = metadata.get("duration_seconds", 30)
        if duration <= 10:
            fps, max_frames = 3, 30
        elif duration <= 30:
            fps, max_frames = 2, 60
        else:
            fps, max_frames = 1, 60
        frames = extract_frames(video_path, frames_dir, fps=fps, max_frames=max_frames)

        # ── Stage 3: Audio extraction ────────────────────────────
        cb("extracting", 20)
        audio_path = extract_audio(video_path, audio_dir)

        # ── Stage 4: Face analysis ───────────────────────────────
        cb("analyzing", 30)
        face_result = analyze_faces(frames)

        # ── Stage 5: Voice analysis ──────────────────────────────
        cb("analyzing", 45)
        voice_result = analyze_voice(audio_path)

        # ── Stage 6: Lip-sync analysis ───────────────────────────
        cb("analyzing", 58)
        lipsync_result = analyze_lipsync(frames, audio_path)

        # ── Stage 7: Blink analysis ──────────────────────────────
        cb("analyzing", 72)
        blink_result = analyze_blinks(frames)

        # ── Stage 8: Head motion analysis ────────────────────────
        cb("analyzing", 82)
        headmotion_result = analyze_headmotion(frames)

        # ── Stage 9: Fusion ──────────────────────────────────────
        cb("analyzing", 92)
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

        cb("completed", 100)

        return {
            **fusion_result,
            # Per-signal scores (0-100)
            "face_score":       face_result["face_score"],
            "voice_score":      voice_result["voice_score"],
            "lipsync_score":    lipsync_result["lipsync_score"],
            "blink_score":      blink_result["blink_score"],
            "headmotion_score": headmotion_result["headmotion_score"],
            # Detailed signal breakdown for frontend
            "signal_details": {
                "face":       face_result.get("details", {}),
                "voice":      voice_result.get("details", {}),
                "lipsync":    lipsync_result.get("details", {}),
                "blink":      blink_result.get("details", {}),
                "headmotion": headmotion_result.get("details", {}),
                "metadata":   metadata,
            },
        }

    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
