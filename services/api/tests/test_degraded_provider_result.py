"""Honest degraded completed payload when Gemini pipeline cannot finish."""

from __future__ import annotations

from app.schemas.clips import ClipResultPayload
from app.services.clip_review_assembly import build_degraded_provider_failure_result


def test_degraded_payload_validates_and_has_no_synthetic_coaching() -> None:
    first = {
        "duration_seconds": 2.1,
        "frames_sampled": 4,
        "motion_detected": True,
        "video_readable": True,
        "review_readiness": "limited",
        "observations": ["short clip"],
    }
    raw = build_degraded_provider_failure_result(
        first,
        "kickflip",
        pipeline_reason="upstream_timeout",
        pipeline_detail="details",
    )
    p = ClipResultPayload.model_validate(raw)
    assert p.schema_version == 1
    assert p.review_readiness == "insufficient"
    assert p.gemini_used is False
    assert p.review_method == "provider_unavailable"
    assert p.skate_clip_review is None
    assert p.normalized_review is None
    assert p.coaching is None
    assert "AI review service did not return" in " ".join(p.processing_notes)
    assert any("[Video pass]" in o for o in p.observations)


def test_degraded_summary_is_not_a_trick_assessment() -> None:
    raw = build_degraded_provider_failure_result(
        {"frames_sampled": 0, "motion_detected": False, "video_readable": False},
        "untagged",
        pipeline_reason="rate_limited",
        pipeline_detail="",
    )
    assert "automated video check" in raw["review_summary"].lower()
    assert "could not complete ai review" in raw["review_summary"].lower()
