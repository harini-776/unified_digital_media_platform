"""
Frame and audio extraction from video files using FFmpeg and OpenCV.
"""
import os
import subprocess
import cv2
import numpy as np
from app.core.config import get_settings

settings = get_settings()


def extract_frames(video_path: str, output_dir: str, fps: int = 2, max_frames: int = 60) -> list[str]:
    """Extract frames from video at specified FPS.

    Args:
        video_path: Path to the video file.
        output_dir: Directory to save extracted frames.
        fps: Frames per second to extract.
        max_frames: Maximum number of frames to extract.

    Returns:
        List of paths to extracted frame images.
    """
    os.makedirs(output_dir, exist_ok=True)
    frame_pattern = os.path.join(output_dir, "frame_%04d.jpg")

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={fps}",
        "-frames:v", str(max_frames),
        "-q:v", "2",
        frame_pattern,
        "-y", "-loglevel", "error",
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    frames = sorted([
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("frame_") and f.endswith(".jpg")
    ])
    return frames[:max_frames]


def extract_audio(video_path: str, output_dir: str) -> str | None:
    """Extract audio track from video as WAV file."""
    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, "audio.wav")

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        audio_path,
        "-y", "-loglevel", "error",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return audio_path if os.path.exists(audio_path) else None
    except subprocess.CalledProcessError:
        return None


def get_video_metadata(video_path: str) -> dict:
    """Get video duration, resolution, and FPS."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {}

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()

    return {
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "duration_seconds": round(duration, 2),
    }
