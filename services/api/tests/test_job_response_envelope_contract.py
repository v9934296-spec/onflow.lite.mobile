"""
Backend job GET shape (flat JSON) is what the mobile client expects by default.

apps/mobile parseJobGet() also accepts the same logical object nested under one of:
data, body, payload, or job (optional gateway wrappers), preferring a candidate that includes
`result` when status is completed.
"""

from app.schemas.clips import (
    ClipResultPayload,
    JobCompletedResponse,
    QualitySignalsPayload,
)


def _minimal_completed(
    job_id: str = "550e8400-e29b-41d4-a716-446655440000",
) -> JobCompletedResponse:
    return JobCompletedResponse(
        job_id=job_id,
        status="completed",
        updated_at="2025-01-01T00:00:00Z",
        result=ClipResultPayload(
            clip_label="session",
            review_summary="summary",
            review_readiness="usable",
            quality_signals=QualitySignalsPayload(
                frames_sampled=1,
                motion_detected=True,
                video_readable=True,
            ),
        ),
    )


def test_completed_job_api_shape_top_level_keys() -> None:
    payload = _minimal_completed().model_dump(mode="json")
    assert payload["job_id"]
    assert payload["status"] == "completed"
    assert payload.get("updated_at")
    assert payload["result"]["analysis_type"] == "skate_clip_review"
    assert payload["result"].get("schema_version") == 1
    assert payload["result"]["quality_signals"]["frames_sampled"] == 1
    assert "review_readiness" in payload["result"]
    assert payload["result"].get("uncertainty_notes") == []
    assert payload["result"].get("video_playback_url") is None
    assert payload["result"].get("thumbnail_url") is None
