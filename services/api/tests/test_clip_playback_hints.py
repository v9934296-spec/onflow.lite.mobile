"""Playback URL attachment for completed clip jobs — sanitized metadata + optional presign."""

from __future__ import annotations

from unittest.mock import patch

from app.core.config import Settings
from app.schemas.clips import ClipResultPayload
from app.services.clip_playback_hints import (
    extract_playback_from_metadata,
    merge_playback_hints_into_result,
    sanitize_public_media_url,
)


def test_sanitize_rejects_embedded_credentials() -> None:
    assert sanitize_public_media_url("https://user:secret@evil.example/file.mp4") is None


def test_sanitize_accepts_https() -> None:
    u = "https://res.cloudinary.com/demo/video/upload/v123/clip.mp4"
    assert sanitize_public_media_url(u) == u


def test_extract_from_flat_metadata() -> None:
    v, t = extract_playback_from_metadata(
        {
            "secure_url": "https://videos.example/original.mp4",
            "thumbnail_url": "https://images.example/t.jpg",
        }
    )
    assert v == "https://videos.example/original.mp4"
    assert t == "https://images.example/t.jpg"


def test_extract_nested_clip_like_dict() -> None:
    v, t = extract_playback_from_metadata(
        {
            "stance": "",
            "clip": {
                "secure_url": "https://cdn.example/file.mov",
                "thumbnailUrl": "https://cdn.example/th.webp",
            },
        }
    )
    assert v == "https://cdn.example/file.mov"
    assert t == "https://cdn.example/th.webp"


def test_merge_sets_video_from_metadata_no_skip_delete() -> None:
    result: dict = {
        "analysis_type": "skate_clip_review",
        "clip_label": "kickflip",
        "review_summary": "ok",
        "review_readiness": "usable",
        "quality_signals": {"frames_sampled": 1, "motion_detected": True, "video_readable": True},
    }
    skip = merge_playback_hints_into_result(
        result,
        clip_metadata={"playback_url": "https://public.example/clip.mp4"},
        storage_key="abc.mp4",
        settings=Settings.model_construct(
            clip_playback_presigned_ttl_seconds=0,
        ),
    )
    assert skip is False
    assert result["video_playback_url"] == "https://public.example/clip.mp4"


def test_merge_presigned_skips_remote_delete() -> None:
    result: dict = {
        "analysis_type": "skate_clip_review",
        "clip_label": "ollie",
        "review_summary": "ok",
        "review_readiness": "usable",
        "quality_signals": {"frames_sampled": 1, "motion_detected": True, "video_readable": True},
        "processing_notes": [],
    }
    signed = "https://bucket.s3.example/presigned?X-Amz-Signature=abc"
    with patch(
        "app.services.clip_playback_hints._presigned_playback_from_s3",
        return_value=signed,
    ):
        skip = merge_playback_hints_into_result(
            result,
            clip_metadata={},
            storage_key="job-id.mp4",
            settings=Settings.model_construct(
                clip_playback_presigned_ttl_seconds=3600,
                s3_bucket="b",
            ),
        )
    assert skip is True
    assert result["video_playback_url"] == signed
    assert any("temporary download link" in n for n in result["processing_notes"])


def test_merge_does_not_overwrite_existing_playback_fields() -> None:
    result: dict = {
        "analysis_type": "skate_clip_review",
        "clip_label": "x",
        "review_summary": "ok",
        "review_readiness": "usable",
        "quality_signals": {"frames_sampled": 1, "motion_detected": True, "video_readable": True},
        "video_playback_url": "https://existing.example/a.mp4",
        "thumbnail_url": "https://existing.example/b.jpg",
    }
    merge_playback_hints_into_result(
        result,
        clip_metadata={
            "video_playback_url": "https://other.example/should-not-win.mp4",
            "thumbnail_url": "https://other.example/ignored.jpg",
        },
        storage_key="k",
        settings=Settings.model_construct(clip_playback_presigned_ttl_seconds=0),
    )
    assert result["video_playback_url"] == "https://existing.example/a.mp4"
    assert result["thumbnail_url"] == "https://existing.example/b.jpg"


def test_clip_result_payload_legacy_json_without_media_fields() -> None:
    p = ClipResultPayload.model_validate(
        {
            "analysis_type": "skate_clip_review",
            "clip_label": "session",
            "review_summary": "summary",
            "review_readiness": "usable",
            "quality_signals": {
                "frames_sampled": 1,
                "motion_detected": True,
                "video_readable": True,
            },
        }
    )
    assert p.schema_version == 1
    assert p.video_playback_url is None
    assert p.thumbnail_url is None
