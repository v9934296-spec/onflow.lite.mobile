"""Rolling session_id for stats rows — time-gap grouping (same user only)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import TrickStatModel

# New attempt continues the same session if within this many seconds of the previous attempt.
SESSION_INACTIVITY_GAP_SECONDS = 90 * 60


def resolve_session_id(session: Session, user_id: str, now: datetime | None = None) -> str:
    """
    Assign session_id for the next TrickStat row(s).

    Rules:
    - Same authenticated user only (caller passes user_id).
    - Continue session if last attempt was within SESSION_INACTIVITY_GAP_SECONDS (90 min).
    - No same-calendar-day requirement — a session can span midnight if the gap stays under the
      threshold (avoids splitting a continuous night session).
    - Gap longer than 90 minutes (or 3+ hours) starts a new session_id.
    """
    n = now or datetime.now(timezone.utc)
    if n.tzinfo is None:
        n = n.replace(tzinfo=timezone.utc)
    stmt = (
        select(TrickStatModel)
        .where(TrickStatModel.user_id == user_id)
        .order_by(TrickStatModel.created_at.desc())
        .limit(1)
    )
    row = session.exec(stmt).first()
    if row and row.session_id:
        last = row.created_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        gap = (n - last).total_seconds()
        if gap >= 0 and gap <= SESSION_INACTIVITY_GAP_SECONDS:
            return row.session_id
    return uuid.uuid4().hex[:16]
