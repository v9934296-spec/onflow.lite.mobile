"""Bridge V1 ``clips`` rows to the legacy ``clip_jobs`` analysis pipeline."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import HTTPException, Request
from sqlmodel import Session

from app.core.config import get_settings
from app.core.tiers import normalize_tier
from app.domain.clip_job import ClipJobRecord, JobAlreadyExists
from app.models import ClipModel, SkateSessionModel
from app.repositories.clip_jobs import ClipJobRepository
from app.schemas.clips import ClipCompleteUploadResponse
from app.services.clip_playback_hints import sanitize_public_media_url
from app.services.clip_quota import (
    begin_quota_release,
    create_job_charging_quota,
    settle_quota_release,
)
from app.services.clip_upload import as_utc, iso_z
from app.services.job_queue import enqueue_clip_job
from app.services.trick_registry import normalize_trick_name
from app.services.video_signature import looks_like_video

logger = structlog.get_logger(__name__)


def assert_session_accepts_clip(
    session: SkateSessionModel,
    *,
    captured_at: datetime | None,
    now: datetime | None = None,
) -> None:
    """Reject clips filmed after ended_at, and uploads that miss the 24h window.

    Open sessions are unrestricted. An ended session still accepts a delayed
    upload when the capture (or, for legacy clients with captured_at omitted,
    window-only) predates ended_at and the request is within the reconciliation
    window. Complete-upload must pass the persisted clip.captured_at — never
    clip.created_at. Structured codes only — clients must not parse prose.
    """
    if session.ended_at is None:
        return
    ended = as_utc(session.ended_at)
    moment = now or datetime.now(timezone.utc)
    hours = max(1, int(get_settings().ended_session_upload_window_hours))
    if moment > ended + timedelta(hours=hours):
        raise HTTPException(
            status_code=409,
            detail="session_end_upload_window_expired",
        )
    if captured_at is not None and as_utc(captured_at) > ended:
        raise HTTPException(
            status_code=409,
            detail="capture_after_session_end",
        )


def clip_model_to_response(
    clip: ClipModel,
    *,
    estimated_analysis_completion_at: datetime | None = None,
) -> ClipCompleteUploadResponse:
    return ClipCompleteUploadResponse(
        id=clip.id,
        user_id=clip.user_id,
        session_id=clip.session_id,
        upload_status=clip.upload_status,
        storage_key=clip.storage_key,
        duration_seconds=clip.duration_seconds,
        width_px=clip.width_px,
        height_px=clip.height_px,
        content_type=clip.content_type,
        trick_id=clip.trick_id,
        thumbnail_url=clip.thumbnail_url,
        landed=clip.landed,
        pte_rating=clip.pte_rating,
        created_at=iso_z(clip.created_at),
        updated_at=iso_z(clip.updated_at),
        estimated_analysis_completion_at=(
            iso_z(estimated_analysis_completion_at)
            if estimated_analysis_completion_at
            else None
        ),
    )


def _load_owned_clip(db: Session, clip_id: str, user_id: str) -> ClipModel:
    clip = db.get(ClipModel, clip_id)
    if clip is None or clip.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Clip not found.")
    if clip.user_id != user_id:
        raise HTTPException(status_code=404, detail="Clip not found.")
    return clip


async def _verify_upload_object(storage: Any, clip: ClipModel) -> int:
    """Existence, size ceiling, and magic-byte sniff. Deletes rejects. Returns size."""
    if not await storage.exists(clip.storage_key):
        raise HTTPException(
            status_code=404,
            detail="Upload not found at storage key — confirm the client PUT succeeded.",
        )

    actual_size = await storage.size(clip.storage_key)
    if actual_size is None or actual_size <= 0:
        await storage.delete(clip.storage_key)
        raise HTTPException(
            status_code=422,
            detail="Uploaded file is empty or unreadable — re-record and upload again.",
        )
    max_upload_bytes = get_settings().clip_max_upload_bytes
    if max_upload_bytes > 0 and actual_size > max_upload_bytes:
        await storage.delete(clip.storage_key)
        raise HTTPException(
            status_code=413,
            detail="Uploaded clip exceeds the maximum allowed size.",
        )

    # Reject non-video payloads before charging quota / enqueueing analysis.
    try:
        local_path = await storage.get_path(clip.storage_key)
    except Exception as exc:
        await storage.delete(clip.storage_key)
        raise HTTPException(
            status_code=422,
            detail="Uploaded file is empty or unreadable — re-record and upload again.",
        ) from exc
    if not looks_like_video(local_path):
        await storage.delete(clip.storage_key)
        raise HTTPException(
            status_code=422,
            detail="Uploaded file is not a recognized video format — re-record and upload again.",
        )
    return actual_size


async def complete_v1_clip_upload(
    request: Request,
    clip_id: str,
    user_id: str,
    db: Session,
) -> ClipCompleteUploadResponse:
    clip = _load_owned_clip(db, clip_id, user_id)

    if clip.session_id:
        session_row = db.get(SkateSessionModel, clip.session_id)
        if session_row is not None and session_row.deleted_at is None:
            assert_session_accepts_clip(session_row, captured_at=clip.captured_at)

    if clip.upload_status == "analyzed":
        raise HTTPException(status_code=409, detail="Clip upload already completed.")
    if clip.upload_status == "analyzing":
        eta = datetime.now(timezone.utc) + timedelta(seconds=45)
        return clip_model_to_response(clip, estimated_analysis_completion_at=eta)

    if clip.upload_status not in ("pending", "failed"):
        raise HTTPException(status_code=409, detail="Clip upload already completed.")

    storage = request.app.state.storage
    actual_size = await _verify_upload_object(storage, clip)
    if actual_size != clip.size_bytes:
        clip.size_bytes = actual_size

    repo: ClipJobRepository = request.app.state.repo
    existing_job = repo.get(clip_id)
    if existing_job is not None and existing_job.status == "completed":
        raise HTTPException(status_code=409, detail="Clip upload already completed.")
    if existing_job is not None and existing_job.status in ("pending", "processing"):
        clip.upload_status = "analyzing"
        clip.updated_at = datetime.now(timezone.utc)
        db.add(clip)
        db.commit()
        db.refresh(clip)
        eta = datetime.now(timezone.utc) + timedelta(seconds=45)
        return clip_model_to_response(clip, estimated_analysis_completion_at=eta)

    label = normalize_trick_name(clip.trick_id) if clip.trick_id else "untagged"
    tricks: list[str] = []
    if clip.trick_id and clip.trick_id.strip():
        tricks = [clip.trick_id.strip().lower()]

    identity = request.app.state.db

    metadata: dict[str, Any] = {
        "tricks": tricks,
        "v1_skate_session_id": clip.session_id,
        "v1_clip_id": clip.id,
    }

    if existing_job is None:
        cc = get_settings().clip_concurrent_processing_limit_per_user
        if cc > 0:
            active = repo.count_active_clip_jobs(user_id)
            if active >= cc:
                raise HTTPException(
                    status_code=429,
                    detail="Too many clips are still processing. Finish or wait before uploading another.",
                )

        def _build(tier_norm: str, quota_src: str | None) -> ClipJobRecord:
            return ClipJobRecord.new_pending(
                clip_id,
                user_id,
                f"storage:{clip.storage_key}",
                clip_label=label,
                tier=tier_norm,
                clip_metadata=metadata,
                quota_source=quota_src,
            )

        try:
            create_job_charging_quota(request, user_id, _build)
        except JobAlreadyExists:
            # Concurrent complete-upload won the insert — treat as in-flight.
            clip.upload_status = "analyzing"
            clip.updated_at = datetime.now(timezone.utc)
            db.add(clip)
            db.commit()
            db.refresh(clip)
            eta = datetime.now(timezone.utc) + timedelta(seconds=45)
            return clip_model_to_response(clip, estimated_analysis_completion_at=eta)
    else:
        # Retry of an already-charged job — recompute tier but never re-charge quota.
        tier_norm = normalize_tier(identity.get_user_tier(user_id))
        existing_job.with_status("pending")
        existing_job.failure_reason = None
        existing_job.result_json = None
        existing_job.clip_metadata = metadata
        existing_job.clip_label = label
        existing_job.input_reference = f"storage:{clip.storage_key}"
        existing_job.tier = tier_norm
        repo.update(existing_job)

    now = datetime.now(timezone.utc)
    clip.upload_status = "analyzing"
    clip.updated_at = now
    db.add(clip)
    db.commit()
    db.refresh(clip)

    try:
        await enqueue_clip_job(
            clip_id,
            clip.storage_key,
            user_id,
            fallback_repo=repo,
            fallback_storage=storage,
        )
    except Exception as exc:
        # Charge already applied; reverse quota and mark failed so the user is
        # not stuck in "analyzing" with a spent free slot / bonus credit.
        logger.exception("enqueue_clip_job_failed job_id=%s", clip_id)
        failed = repo.get(clip_id)
        if failed is not None and failed.status in ("pending", "processing"):
            release = begin_quota_release(failed)
            failed.with_status("failed", failure_reason="enqueue_failed")
            repo.update(failed)
            settle_quota_release(
                identity,
                user_id,
                release,
                job_id=clip_id,
                reason="enqueue_failed",
            )
        clip.upload_status = "failed"
        clip.updated_at = datetime.now(timezone.utc)
        db.add(clip)
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Could not queue clip analysis. Please retry complete-upload.",
        ) from exc

    eta = now + timedelta(seconds=45)
    return clip_model_to_response(clip, estimated_analysis_completion_at=eta)


def sync_v1_clip_from_job_result(
    job_id: str,
    result: dict[str, Any] | None,
    *,
    failed: bool = False,
) -> None:
    """Mirror clip_jobs terminal state onto the V1 ``clips`` row when present."""
    from app.core.database import get_engine

    engine = get_engine()
    with Session(engine) as session:
        clip = session.get(ClipModel, job_id)
        if clip is None or clip.deleted_at is not None:
            return
        now = datetime.now(timezone.utc)
        if failed:
            clip.upload_status = "failed"
        else:
            clip.upload_status = "analyzed"
            landed_raw = (result or {}).get("landed")
            if landed_raw == "yes":
                clip.landed = True
            elif landed_raw == "no":
                clip.landed = False
            score = (result or {}).get("land_score")
            if score is None:
                norm = (result or {}).get("normalized_review") or {}
                if isinstance(norm, dict):
                    score = norm.get("score")
            if isinstance(score, (int, float)):
                clip.pte_rating = int(round(float(score)))
            thumb = sanitize_public_media_url((result or {}).get("thumbnail_url"))
            if thumb:
                clip.thumbnail_url = thumb
            label = (result or {}).get("clip_label")
            if isinstance(label, str) and label.strip() and not clip.trick_id:
                clip.trick_id = label.strip().lower()
        clip.updated_at = now
        session.add(clip)
        session.commit()
