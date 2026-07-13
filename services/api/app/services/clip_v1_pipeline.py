"""Bridge V1 ``clips`` rows to the legacy ``clip_jobs`` analysis pipeline."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request
from sqlmodel import Session

from app.core.config import get_settings
from app.core.tiers import normalize_tier
from app.domain.clip_job import ClipJobRecord
from app.models import ClipModel
from app.repositories.clip_jobs import ClipJobRepository
from app.schemas.clips import ClipCompleteUploadResponse
from app.services.clip_playback_hints import sanitize_public_media_url
from app.services.clip_quota import reserve_clip_submission
from app.services.clip_upload import iso_z
from app.services.job_queue import enqueue_clip_job
from app.services.trick_registry import normalize_trick_name


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


async def complete_v1_clip_upload(
    request: Request,
    clip_id: str,
    user_id: str,
    db: Session,
) -> ClipCompleteUploadResponse:
    clip = _load_owned_clip(db, clip_id, user_id)

    if clip.upload_status == "analyzed":
        raise HTTPException(status_code=409, detail="Clip upload already completed.")
    if clip.upload_status == "analyzing":
        eta = datetime.now(timezone.utc) + timedelta(seconds=45)
        return clip_model_to_response(clip, estimated_analysis_completion_at=eta)

    if clip.upload_status not in ("pending", "failed"):
        raise HTTPException(status_code=409, detail="Clip upload already completed.")

    storage = request.app.state.storage
    if not await storage.exists(clip.storage_key):
        raise HTTPException(
            status_code=404,
            detail="Upload not found at storage key — confirm the client PUT succeeded.",
        )

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

        # First real completion → charge the product quota now (mirrors the legacy
        # reserve-at-create) and record how it was charged so monthly-free accounting
        # stays correct. Raises 429 if the user is over quota with no bonus left;
        # the clip row stays "pending" and nothing is enqueued.
        tier_norm, quota_src = reserve_clip_submission(request, user_id)
        record = ClipJobRecord.new_pending(
            clip_id,
            user_id,
            f"storage:{clip.storage_key}",
            clip_label=label,
            tier=tier_norm,
            clip_metadata=metadata,
            quota_source=quota_src,
        )
        repo.create(record)
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

    await enqueue_clip_job(
        clip_id,
        clip.storage_key,
        user_id,
        fallback_repo=repo,
        fallback_storage=storage,
    )

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
