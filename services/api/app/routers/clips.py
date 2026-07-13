from __future__ import annotations

import logging
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import get_current_user
from app.repositories.clip_jobs import ClipJobRepository
from app.schemas.clips import (
    ClipResultPayload,
    JobCompletedResponse,
    JobFailedResponse,
    JobListItem,
    JobPendingResponse,
    JobProcessingResponse,
)
from app.services.clip_playback_hints import sanitize_public_media_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/clips/jobs", tags=["clips"])


def _repo(request: Request) -> ClipJobRepository:
    return request.app.state.repo


def _job_updated_iso(record) -> str:
    dt = record.updated_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _clip_media_from_record(record) -> tuple[str | None, str | None]:
    result = record.result_json or {}
    metadata = record.clip_metadata or {}

    video = sanitize_public_media_url(result.get("video_playback_url"))
    thumb = sanitize_public_media_url(result.get("thumbnail_url"))

    if not video:
        video = sanitize_public_media_url(metadata.get("video_playback_url"))

    if not thumb:
        thumb = sanitize_public_media_url(metadata.get("thumbnail_url"))

    return video, thumb


@router.get("", response_model=list[JobListItem], response_model_exclude_none=True)
async def list_clip_jobs(
    request: Request,
    limit: int = 30,
    user_id: str = Depends(get_current_user),
) -> list[JobListItem]:
    rows = _repo(request).list_full_for_user(user_id, limit=limit)

    out: list[JobListItem] = []

    for record in rows:
        video_url, thumb_url = _clip_media_from_record(record)

        out.append(
            JobListItem(
                job_id=record.id,
                status=record.status,
                clip_label=record.clip_label or "untagged",
                updated_at=_job_updated_iso(record),
                failure_reason=record.failure_reason,
                video_playback_url=video_url,
                thumbnail_url=thumb_url,
            )
        )

    return out


@router.get("/{job_id}", response_model_exclude_none=True)
async def get_clip_job(
    request: Request,
    job_id: str,
    user_id: str = Depends(get_current_user),
) -> JobPendingResponse | JobProcessingResponse | JobCompletedResponse | JobFailedResponse:
    record = _repo(request).get_for_user(job_id, user_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    ts = _job_updated_iso(record)

    if record.status == "pending":
        return JobPendingResponse(job_id=record.id, status="pending", updated_at=ts)

    if record.status == "processing":
        return JobProcessingResponse(job_id=record.id, status="processing", updated_at=ts)

    if record.status == "failed":
        return JobFailedResponse(
            job_id=record.id,
            status="failed",
            updated_at=ts,
            failure_reason=record.failure_reason or "unknown",
        )

    raw = record.result_json

    if raw is None:
        logger.warning(
            "completed_job_missing_result_json job_id=%s user_id=%s",
            job_id,
            user_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Completed job is missing result data.",
        )

    return JobCompletedResponse(
        job_id=record.id,
        status="completed",
        updated_at=ts,
        result=ClipResultPayload.model_validate(raw),
    )
