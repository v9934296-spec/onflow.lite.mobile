"""Unit tests for first-pass video analysis helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.video_first_pass import _normalize_readiness


def test_readiness_insufficient_when_unreadable() -> None:
    assert (
        _normalize_readiness(
            video_readable=False,
            frames_sampled=0,
            duration_seconds=None,
            mean_brightness=None,
            motion_detected=False,
            laplacian_var_mean=None,
        )
        == "insufficient"
    )


def test_readiness_insufficient_dark() -> None:
    assert (
        _normalize_readiness(
            video_readable=True,
            frames_sampled=10,
            duration_seconds=2.0,
            mean_brightness=0.03,
            motion_detected=True,
            laplacian_var_mean=None,
        )
        == "insufficient"
    )


def test_readiness_limited_short_duration() -> None:
    assert (
        _normalize_readiness(
            video_readable=True,
            frames_sampled=10,
            duration_seconds=0.2,
            mean_brightness=0.5,
            motion_detected=True,
            laplacian_var_mean=None,
        )
        == "limited"
    )


def test_readiness_usable_typical() -> None:
    assert (
        _normalize_readiness(
            video_readable=True,
            frames_sampled=12,
            duration_seconds=2.0,
            mean_brightness=0.4,
            motion_detected=True,
            laplacian_var_mean=80.0,
        )
        == "usable"
    )


def test_readiness_insufficient_very_blurry() -> None:
    assert (
        _normalize_readiness(
            video_readable=True,
            frames_sampled=12,
            duration_seconds=2.0,
            mean_brightness=0.4,
            motion_detected=True,
            laplacian_var_mean=5.0,
        )
        == "insufficient"
    )


def test_readiness_limited_moderate_blur() -> None:
    assert (
        _normalize_readiness(
            video_readable=True,
            frames_sampled=12,
            duration_seconds=2.0,
            mean_brightness=0.4,
            motion_detected=True,
            laplacian_var_mean=20.0,
        )
        == "limited"
    )


def test_analyze_nonexistent_file(tmp_path: Path) -> None:
    pytest.importorskip("cv2")
    from app.services.video_first_pass import analyze_video_first_pass

    out = analyze_video_first_pass(str(tmp_path / "missing.mp4"))
    assert out["video_readable"] is False
    assert out["review_readiness"] == "insufficient"
