"""Generate feed events from product actions (Step 5C — session_recap on session end)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.models import ClipModel, FeedEventModel, SessionAttemptModel, SkateSessionModel
from app.services.trick_registry import normalize_trick_name

SESSION_RECAP_VERSION = "feed_1.0.0"


def _tricks_attempted(
    db: Session, session_id: str, focus_trick: str | None
) -> list[str]:
    stmt = (
        select(ClipModel.trick_id)
        .where(
            ClipModel.session_id == session_id,
            ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
            ClipModel.trick_id.isnot(None),  # type: ignore[union-attr]
        )
        .distinct()
    )
    names: list[str] = []
    seen: set[str] = set()
    if focus_trick and focus_trick.strip():
        key = focus_trick.strip().lower()
        seen.add(key)
        names.append(focus_trick.strip())
    for trick_id in db.exec(stmt):
        if not trick_id:
            continue
        key = trick_id.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(normalize_trick_name(trick_id) or trick_id)
    return names


def find_session_recap_event(
    db: Session, *, user_id: str, session_id: str
) -> FeedEventModel | None:
    stmt = select(FeedEventModel).where(
        FeedEventModel.user_id == user_id,
        FeedEventModel.event_type == "session_recap",
        FeedEventModel.skate_session_id == session_id,
        FeedEventModel.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    return db.exec(stmt).first()


def generate_session_recap_feed_event(
    db: Session, session_id: str, *, user_id: str | None = None
) -> FeedEventModel | None:
    """
    Create a propagated session_recap feed event when a skate session ends.
    Idempotent per (user_id, skate_session_id).
    """
    row = db.get(SkateSessionModel, session_id)
    if row is None or row.deleted_at is not None:
        return None
    if row.ended_at is None:
        return None
    owner_id = user_id or row.user_id
    if row.user_id != owner_id:
        return None

    existing = find_session_recap_event(db, user_id=owner_id, session_id=session_id)
    if existing is not None:
        return existing

    clip_stmt = select(func.count(ClipModel.id)).where(
        ClipModel.session_id == session_id,
        ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    clip_count = int(db.exec(clip_stmt).one())
    attempt_stmt = select(func.count(SessionAttemptModel.id)).where(
        SessionAttemptModel.session_id == session_id,
        SessionAttemptModel.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    attempt_count = int(db.exec(attempt_stmt).one())
    breakthrough_note = (row.breakthrough_note or "").strip() or None
    breakthrough_count = 1 if breakthrough_note else 0
    completed_at = row.ended_at or datetime.now(timezone.utc)

    payload = {
        "session_id": row.id,
        "spot_label": row.spot_label,
        "clip_count": clip_count,
        "attempt_count": attempt_count,
        "tricks_attempted": _tricks_attempted(db, session_id, row.focus_trick),
        "breakthrough_note": breakthrough_note,
        "breakthrough_count": breakthrough_count,
        "focus_trick": row.focus_trick,
        "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
    }

    now = datetime.now(timezone.utc)
    event = FeedEventModel(
        id=str(uuid.uuid4()),
        user_id=owner_id,
        event_type="session_recap",
        event_version=SESSION_RECAP_VERSION,
        skate_session_id=row.id,
        trick_id=row.focus_trick,
        clip_id=None,
        payload_json=json.dumps(payload),
        generated_at=now,
        propagates_at=now,
        propagation_status="propagated",
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent end-session call. The DB unique guard
        # rejected the duplicate; return the row the winner inserted.
        db.rollback()
        return find_session_recap_event(db, user_id=owner_id, session_id=session_id)
    db.refresh(event)
    from app.services.feed_sse_notify import notify_feed_event_created

    notify_feed_event_created(db, event)
    return event
