"""Match completed clip trick lists to saved custom lines and record attempts."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import CustomLineModel, LineAttemptModel


def record_matching_line_attempts(
    session: Session,
    *,
    user_id: str,
    job_id: str,
    clip_tricks: list[str],
    landed: str | None,
    session_id: str,
) -> None:
    """
    If the clip's ordered trick list exactly matches a user's saved line sequence,
    insert a LineAttemptModel (once per job per line).
    Clip trick count is capped at 3 at upload; lines may be 2–6 tricks — only exact
    equality matches (same length and order).
    """
    if len(clip_tricks) < 2:
        return

    stmt = select(CustomLineModel).where(CustomLineModel.user_id == user_id)
    lines = list(session.exec(stmt))
    for line in lines:
        seq = line.trick_sequence
        if len(seq) < 2 or seq != clip_tricks:
            continue
        existing = session.exec(
            select(LineAttemptModel).where(
                LineAttemptModel.line_id == line.id,
                LineAttemptModel.job_id == job_id,
            )
        ).first()
        if existing:
            continue
        session.add(
            LineAttemptModel(
                user_id=user_id,
                line_id=line.id,
                job_id=job_id,
                landed=landed,
                session_id=session_id,
            )
        )
