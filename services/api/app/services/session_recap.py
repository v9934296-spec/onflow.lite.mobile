"""Session recap aggregation for the progression detail view (Step 5E).

Aggregates a single skate session + its clips into a richer recap than the lean
feed payload. Uses existing data only — any metric that cannot be derived
honestly is returned as ``None`` rather than a guessed/zero value.

Clip ordering: **newest-first** (``created_at`` descending).
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import ClipModel, SkateSessionModel
from app.schemas.sessions import SessionRecapClip, SessionRecapDetailResponse
from app.services.clip_upload import iso_z
from app.services.trick_registry import normalize_trick_name


def _playback_url(storage_url: str | None) -> str | None:
    url = (storage_url or "").strip()
    return url or None


def build_session_recap_detail(
    db: Session, session_id: str, *, user_id: str
) -> SessionRecapDetailResponse | None:
    """Owner-scoped recap aggregation. Returns ``None`` when the session is
    missing, soft-deleted, or owned by another user (caller maps to 404)."""
    row = db.get(SkateSessionModel, session_id)
    if row is None or row.deleted_at is not None or row.user_id != user_id:
        return None

    clip_rows = list(
        db.exec(
            select(ClipModel)
            .where(
                ClipModel.session_id == session_id,
                ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            .order_by(ClipModel.created_at.desc())
        )
    )

    clips_count = len(clip_rows)
    attempts_count = clips_count  # V1: one clip == one attempt

    landed_known = [c for c in clip_rows if c.landed is not None]
    if landed_known:
        landed_count: int | None = sum(1 for c in clip_rows if c.landed is True)
        landed_rate: float | None = (
            round(landed_count / clips_count, 2) if clips_count else None
        )
    else:
        landed_count = None
        landed_rate = None

    pte_known = [c.pte_rating for c in clip_rows if c.pte_rating is not None]
    best_pte_score = float(max(pte_known)) if pte_known else None
    average_pte_score = round(sum(pte_known) / len(pte_known), 1) if pte_known else None

    duration_seconds: int | None = None
    if row.ended_at is not None:
        delta = (row.ended_at - row.started_at).total_seconds()
        duration_seconds = int(delta) if delta >= 0 else None

    clips = [
        SessionRecapClip(
            clip_id=c.id,
            thumbnail_url=c.thumbnail_url,
            video_playback_url=_playback_url(c.storage_url),
            trick=(normalize_trick_name(c.trick_id) or c.trick_id) if c.trick_id else None,
            stance=None,  # no per-clip stance on ClipModel in V1
            landed=c.landed,
            pte_score=c.pte_rating,
            created_at=iso_z(c.created_at),
        )
        for c in clip_rows
    ]

    return SessionRecapDetailResponse(
        session_id=row.id,
        started_at=iso_z(row.started_at),
        ended_at=iso_z(row.ended_at) if row.ended_at else None,
        duration_seconds=duration_seconds,
        spot=row.spot_label,
        focus_trick=row.focus_trick,
        clips_count=clips_count,
        attempts_count=attempts_count,
        landed_count=landed_count,
        landed_rate=landed_rate,
        best_pte_score=best_pte_score,
        average_pte_score=average_pte_score,
        breakthrough_note=row.breakthrough_note,
        clips=clips,
    )
