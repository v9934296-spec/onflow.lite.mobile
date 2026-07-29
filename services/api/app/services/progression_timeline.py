"""Progression timeline aggregation (Step 5F).

Owner-scoped, offset-paginated list of a skater's completed sessions, newest-first.
Reuses the existing session/clip tables — no schema changes. Each entry is a
lightweight preview (the full recap lives behind the 5E recap-detail endpoint).

Ordering: **newest-first** by ``ended_at`` (tie-break ``id`` descending).
Scope: only ended, non-deleted sessions owned by the user.
"""
from __future__ import annotations

from sqlmodel import Session, func, select

from app.models import ClipModel, SkateSessionModel
from app.schemas.progression import ProgressionTimelineItem
from app.services.clip_upload import iso_z


def _timeline_aggregates(
    db: Session, session_ids: list[str]
) -> tuple[dict[str, int], dict[str, float], dict[str, str]]:
    """Batch per-session preview metrics in 3 grouped queries (avoids N+1 over clips).

    Returns (clips_count_by_session, best_pte_by_session, latest_thumbnail_by_session).
    """
    if not session_ids:
        return {}, {}, {}

    count_rows = db.exec(
        select(ClipModel.session_id, func.count(ClipModel.id))
        .where(
            ClipModel.session_id.in_(session_ids),  # type: ignore[union-attr]
            ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .group_by(ClipModel.session_id)
    ).all()
    counts = {sid: int(c) for sid, c in count_rows}

    pte_rows = db.exec(
        select(ClipModel.session_id, func.max(ClipModel.pte_rating))
        .where(
            ClipModel.session_id.in_(session_ids),  # type: ignore[union-attr]
            ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
            ClipModel.pte_rating.isnot(None),  # type: ignore[union-attr]
        )
        .group_by(ClipModel.session_id)
    ).all()
    best_pte = {sid: float(v) for sid, v in pte_rows if v is not None}

    thumb_rows = db.exec(
        select(ClipModel.session_id, ClipModel.thumbnail_url)
        .where(
            ClipModel.session_id.in_(session_ids),  # type: ignore[union-attr]
            ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
            ClipModel.thumbnail_url.isnot(None),  # type: ignore[union-attr]
        )
        .order_by(ClipModel.created_at.desc())
    ).all()
    thumbs: dict[str, str] = {}
    for sid, url in thumb_rows:
        if url and sid not in thumbs:
            thumbs[sid] = url

    return counts, best_pte, thumbs


def _session_to_item(
    row: SkateSessionModel,
    *,
    clips_count: int,
    best_pte_score: float | None,
    thumbnail_url: str | None,
) -> ProgressionTimelineItem:
    duration_seconds: int | None = None
    if row.ended_at is not None:
        delta = (row.ended_at - row.started_at).total_seconds()
        duration_seconds = int(delta) if delta >= 0 else None

    return ProgressionTimelineItem(
        session_id=row.id,
        ended_at=iso_z(row.ended_at) if row.ended_at else None,
        spot=row.spot_label,
        focus_trick=row.focus_trick,
        duration_seconds=duration_seconds,
        clips_count=clips_count,
        best_pte_score=best_pte_score,
        thumbnail_url=thumbnail_url,
    )


def list_progression_timeline(
    db: Session, user_id: str, *, page: int, page_size: int
) -> tuple[list[ProgressionTimelineItem], bool]:
    """Return ``(items, has_more)`` for one page of the user's ended sessions."""
    offset = (page - 1) * page_size
    stmt = (
        select(SkateSessionModel)
        .where(
            SkateSessionModel.user_id == user_id,
            SkateSessionModel.deleted_at.is_(None),  # type: ignore[union-attr]
            SkateSessionModel.ended_at.isnot(None),  # type: ignore[union-attr]
        )
        .order_by(SkateSessionModel.ended_at.desc(), SkateSessionModel.id.desc())
        .offset(offset)
        .limit(page_size + 1)
    )
    rows = list(db.exec(stmt))
    has_more = len(rows) > page_size
    rows = rows[:page_size]

    counts, best_pte, thumbs = _timeline_aggregates(db, [row.id for row in rows])
    items = [
        _session_to_item(
            row,
            clips_count=counts.get(row.id, 0),
            best_pte_score=best_pte.get(row.id),
            thumbnail_url=thumbs.get(row.id),
        )
        for row in rows
    ]
    return items, has_more
