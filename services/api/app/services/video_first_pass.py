"""
Honest first-pass skate clip analysis from the file alone (no trick detection).

Uses OpenCV to open the container, estimate timing, sample frames, and derive
simple motion / brightness heuristics. All outputs are tied to what we actually computed.
"""
from __future__ import annotations

from typing import Any, Literal

import cv2
import numpy as np
import structlog

logger = structlog.get_logger(__name__)

Readiness = Literal["usable", "limited", "insufficient"]

MAX_FRAMES_TO_READ = 420
MAX_SAMPLES = 24
TARGET_WIDTH = 160
MIN_DURATION_INSUFFICIENT = 0.12
MIN_DURATION_LIMITED = 0.35
BRIGHTNESS_INSUFFICIENT = 0.05
BRIGHTNESS_LIMITED = 0.09
MOTION_THRESHOLD = 2.1  # mean |Δ| on 0–255 grayscale between consecutive samples
# Laplacian variance on downscaled grayscale (160px wide). Lower = softer / blurrier samples.
BLUR_INSUFFICIENT = 10.0
BLUR_LIMITED = 28.0


def _normalize_readiness(
    *,
    video_readable: bool,
    frames_sampled: int,
    duration_seconds: float | None,
    mean_brightness: float | None,
    motion_detected: bool,
    laplacian_var_mean: float | None,
) -> Readiness:
    if not video_readable or frames_sampled < 2:
        return "insufficient"
    if duration_seconds is not None and duration_seconds < MIN_DURATION_INSUFFICIENT:
        return "insufficient"
    if mean_brightness is not None and mean_brightness < BRIGHTNESS_INSUFFICIENT:
        return "insufficient"
    if laplacian_var_mean is not None and laplacian_var_mean < BLUR_INSUFFICIENT:
        return "insufficient"
    if duration_seconds is not None and duration_seconds < MIN_DURATION_LIMITED:
        return "limited"
    if mean_brightness is not None and mean_brightness < BRIGHTNESS_LIMITED:
        return "limited"
    if laplacian_var_mean is not None and laplacian_var_mean < BLUR_LIMITED:
        return "limited"
    if frames_sampled < 6:
        return "limited"
    if not motion_detected:
        return "limited"
    return "usable"


def analyze_video_first_pass(file_path: str) -> dict[str, Any]:
    """
    Inspect an on-disk video file. Returns a dict used to build the public API result.
    """
    video_readable = False
    duration_seconds: float | None = None
    fps: float | None = None
    frame_count_prop: int | None = None
    frames_read = 0
    frames_sampled = 0
    motion_detected = False
    mean_brightness: float | None = None
    observations: list[str] = []
    processing_notes: list[str] = [
        "OnFlow does not classify tricks in this build.",
        "This pass uses real frame sampling and simple motion/brightness checks — not coaching scores.",
    ]

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        logger.info("video_first_pass: could not open %s", file_path)
        return _unreadable_outcome()

    try:
        fps_raw = cap.get(cv2.CAP_PROP_FPS)
        fps = float(fps_raw) if fps_raw and fps_raw > 0.5 else None
        fc_raw = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        frame_count_prop = int(fc_raw) if fc_raw and fc_raw > 0 else None
        if fps and frame_count_prop and frame_count_prop > 0:
            duration_seconds = frame_count_prop / fps

        grays: list[np.ndarray] = []
        while frames_read < MAX_FRAMES_TO_READ:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            video_readable = True
            frames_read += 1
            small = cv2.resize(frame, (TARGET_WIDTH, max(2, int(TARGET_WIDTH * frame.shape[0] / frame.shape[1]))))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            grays.append(gray)

        if not grays:
            return _unreadable_outcome()

        n = len(grays)
        if n <= MAX_SAMPLES:
            sampled = grays
        else:
            idxs = np.linspace(0, n - 1, num=MAX_SAMPLES, dtype=int)
            sampled = [grays[int(i)] for i in idxs]

        frames_sampled = len(sampled)
        mean_brightness = float(np.mean(sampled[-1])) / 255.0

        laplacian_vars: list[float] = []
        for gray in sampled:
            lap = cv2.Laplacian(gray, cv2.CV_64F)
            laplacian_vars.append(float(lap.var()))
        laplacian_var_mean = float(np.mean(laplacian_vars)) if laplacian_vars else None

        if frames_sampled >= 2:
            deltas: list[float] = []
            for a, b in zip(sampled[:-1], sampled[1:]):
                deltas.append(float(np.mean(cv2.absdiff(a, b))))
            mean_delta = float(np.mean(deltas)) if deltas else 0.0
            motion_detected = mean_delta >= MOTION_THRESHOLD

        if duration_seconds is None and fps and frames_read > 0:
            duration_seconds = frames_read / fps

        readiness = _normalize_readiness(
            video_readable=True,
            frames_sampled=frames_sampled,
            duration_seconds=duration_seconds,
            mean_brightness=mean_brightness,
            motion_detected=motion_detected,
            laplacian_var_mean=laplacian_var_mean,
        )

        if video_readable:
            observations.append("Video container opened and frames were read.")
        if duration_seconds is not None:
            observations.append(f"Estimated duration ~{duration_seconds:.2f}s (from metadata or read loop).")
        observations.append(f"Sampled {frames_sampled} frame(s) for motion and brightness checks.")
        if motion_detected:
            observations.append("Frame-to-frame difference suggests visible motion in sampled frames.")
        else:
            observations.append("Little frame-to-frame change in samples — static camera, very short clip, or low motion.")

        if mean_brightness is not None and mean_brightness < BRIGHTNESS_LIMITED:
            observations.append("Average brightness in samples is low — the clip may be hard to review visually.")
        if laplacian_var_mean is not None:
            if laplacian_var_mean < BLUR_INSUFFICIENT:
                observations.append(
                    "Sampled frames look very soft or blurry (low edge sharpness) — detail for review is likely poor."
                )
            elif laplacian_var_mean < BLUR_LIMITED:
                observations.append(
                    "Sampled frames are somewhat soft — fine mechanics may be harder to judge than on a crisp capture."
                )

        review_summary_base = _summary_for_readiness(readiness, motion_detected, mean_brightness)

        return {
            "video_readable": True,
            "duration_seconds": duration_seconds,
            "fps": fps,
            "frame_count_estimated": frame_count_prop,
            "frames_sampled": frames_sampled,
            "motion_detected": motion_detected,
            "mean_brightness_0_1": mean_brightness,
            "laplacian_var_mean": laplacian_var_mean,
            "review_readiness": readiness,
            "observations": observations,
            "processing_notes": processing_notes,
            "review_summary_base": review_summary_base,
        }
    finally:
        cap.release()


def _unreadable_outcome() -> dict[str, Any]:
    return {
        "video_readable": False,
        "duration_seconds": None,
        "fps": None,
        "frame_count_estimated": None,
        "frames_sampled": 0,
        "motion_detected": False,
        "mean_brightness_0_1": None,
        "laplacian_var_mean": None,
        "review_readiness": "insufficient",
        "observations": ["Could not decode video frames from this file."],
        "processing_notes": [
            "OnFlow does not classify tricks in this build.",
        ],
        "review_summary_base": "We could not read frames from this clip.",
    }


def _summary_for_readiness(
    readiness: Readiness,
    motion_detected: bool,
    mean_brightness: float | None,
) -> str:
    if readiness == "insufficient":
        return (
            "Clip technical pass: readability or length/brightness is below what we treat as review-ready in this beta."
        )
    if readiness == "limited":
        parts = [
            "Clip technical pass: processed with frame sampling.",
            "Useful for basic quality checks; deeper skate-specific interpretation is still limited in this build.",
        ]
        if not motion_detected:
            parts.append("Motion across samples was weak — interpret that as a capture limitation, not a trick call.")
        if mean_brightness is not None and mean_brightness < BRIGHTNESS_LIMITED:
            parts.append("Image exposure looks marginal in samples.")
        return " ".join(parts)
    return (
        "Clip technical pass: readable duration, sampling, and motion check look usable for continued beta review. "
        "This is infrastructure-level analysis — not trick naming or scoring."
    )
