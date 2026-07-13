"""P.T.E. Tech 1.0 — milestone detection and recording."""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.models import MilestoneModel, TrickStatModel

logger = logging.getLogger(__name__)

# ── All 1.0 milestone keys ──
MILESTONE_KEYS = [
    "first_make",
    "locked_in",
    "dialed",
    "new_trick",
    "session_grind",
    "line_landed",
]


def _already_achieved(
    session: Session,
    user_id: str,
    milestone_key: str,
    *,
    trick_name: str | None = None,
    session_id: str | None = None,
    job_id: str | None = None,
) -> bool:
    """Check if this specific milestone instance already exists."""
    stmt = select(MilestoneModel).where(
        MilestoneModel.user_id == user_id,
        MilestoneModel.milestone_key == milestone_key,
    )
    if trick_name is not None:
        stmt = stmt.where(MilestoneModel.trick_name == trick_name)
    if session_id is not None:
        stmt = stmt.where(MilestoneModel.session_id == session_id)
    if job_id is not None:
        stmt = stmt.where(MilestoneModel.job_id == job_id)
    return session.exec(stmt).first() is not None


def _award(
    session: Session,
    user_id: str,
    milestone_key: str,
    *,
    trick_name: str | None = None,
    session_id: str | None = None,
    dedupe_job_id: str | None = None,
    source_job_id: str | None = None,
    awarded: list[MilestoneModel] | None = None,
) -> MilestoneModel | None:
    """
    Write a milestone row. Returns the new row, or None if already achieved.

    dedupe_job_id — only for uniqueness checks (e.g. line_landed per job).
    source_job_id — clip job that triggered this unlock (stored for client results UX).
    """
    if _already_achieved(
        session,
        user_id,
        milestone_key,
        trick_name=trick_name,
        session_id=session_id,
        job_id=dedupe_job_id,
    ):
        return None
    m = MilestoneModel(
        user_id=user_id,
        milestone_key=milestone_key,
        trick_name=trick_name,
        session_id=session_id,
        job_id=source_job_id,
    )
    session.add(m)
    if awarded is not None:
        awarded.append(m)
    logger.info(
        "Milestone unlocked: user=%s key=%s trick=%s",
        user_id,
        milestone_key,
        trick_name or "-",
    )
    return m


def _check_first_make(
    session: Session,
    user_id: str,
    trick_name: str,
    landed: str | None,
    source_job_id: str,
    awarded: list[MilestoneModel],
) -> None:
    """First Make — first landed == "yes" for this trick."""
    if landed != "yes":
        return
    _award(
        session,
        user_id,
        "first_make",
        trick_name=trick_name,
        source_job_id=source_job_id,
        awarded=awarded,
    )


def _check_new_trick(
    session: Session,
    user_id: str,
    trick_name: str,
    source_job_id: str,
    awarded: list[MilestoneModel],
) -> None:
    """New Trick — trick_name appears for the first time in trick_stats."""
    stmt = select(TrickStatModel).where(
        TrickStatModel.user_id == user_id,
        TrickStatModel.trick_name == trick_name,
    )
    rows = list(session.exec(stmt))
    # If this is the only row (just inserted), it's a new trick
    if len(rows) == 1:
        _award(
            session,
            user_id,
            "new_trick",
            trick_name=trick_name,
            source_job_id=source_job_id,
            awarded=awarded,
        )


def _check_locked_in(
    session: Session,
    user_id: str,
    trick_name: str,
    session_id: str | None,
    landed: str | None,
    source_job_id: str,
    awarded: list[MilestoneModel],
) -> None:
    """Locked In — 3 consecutive landed == "yes" for one trick in a single session."""
    if landed != "yes" or not session_id:
        return
    stmt = (
        select(TrickStatModel)
        .where(
            TrickStatModel.user_id == user_id,
            TrickStatModel.trick_name == trick_name,
            TrickStatModel.session_id == session_id,
        )
        .order_by(TrickStatModel.created_at.desc())
        .limit(3)
    )
    rows = list(session.exec(stmt))
    if len(rows) >= 3 and all(r.landed == "yes" for r in rows):
        _award(
            session,
            user_id,
            "locked_in",
            trick_name=trick_name,
            session_id=session_id,
            source_job_id=source_job_id,
            awarded=awarded,
        )


def _check_dialed(
    session: Session,
    user_id: str,
    trick_name: str,
    landed: str | None,
    source_job_id: str,
    awarded: list[MilestoneModel],
) -> None:
    """Dialed — 5 consecutive landed == "yes" for one trick (any sessions)."""
    if landed != "yes":
        return
    stmt = (
        select(TrickStatModel)
        .where(
            TrickStatModel.user_id == user_id,
            TrickStatModel.trick_name == trick_name,
        )
        .order_by(TrickStatModel.created_at.desc())
        .limit(5)
    )
    rows = list(session.exec(stmt))
    if len(rows) >= 5 and all(r.landed == "yes" for r in rows):
        _award(
            session,
            user_id,
            "dialed",
            trick_name=trick_name,
            source_job_id=source_job_id,
            awarded=awarded,
        )


def _check_session_grind(
    session: Session,
    user_id: str,
    session_id: str | None,
    source_job_id: str,
    awarded: list[MilestoneModel],
) -> None:
    """Session Grind — 5+ trick_stats rows in a single session."""
    if not session_id:
        return
    stmt = select(TrickStatModel).where(
        TrickStatModel.user_id == user_id,
        TrickStatModel.session_id == session_id,
    )
    count = len(list(session.exec(stmt)))
    if count >= 5:
        _award(
            session,
            user_id,
            "session_grind",
            session_id=session_id,
            source_job_id=source_job_id,
            awarded=awarded,
        )


def _check_line_landed(
    session: Session,
    user_id: str,
    job_id: str,
    landed: str | None,
    tricks_count: int,
    awarded: list[MilestoneModel],
) -> None:
    """Line Landed — clip with 2+ tricks in metadata where landed == "yes"."""
    if landed != "yes" or tricks_count < 2:
        return
    _award(
        session,
        user_id,
        "line_landed",
        dedupe_job_id=job_id,
        source_job_id=job_id,
        awarded=awarded,
    )


def check_milestones(
    session: Session,
    *,
    user_id: str,
    job_id: str,
    trick_name: str,
    landed: str | None,
    session_id: str | None,
    tricks_in_clip: int,
) -> list[MilestoneModel]:
    """
    Run all milestone checks after a trick stat is recorded.
    Call this AFTER the TrickStatModel row has been added and flushed
    (but before commit — all writes happen in the same transaction).

    Returns list of newly awarded milestones (may be empty).
    """
    awarded: list[MilestoneModel] = []

    try:
        _check_new_trick(session, user_id, trick_name, job_id, awarded)
        _check_first_make(session, user_id, trick_name, landed, job_id, awarded)
        _check_locked_in(session, user_id, trick_name, session_id, landed, job_id, awarded)
        _check_dialed(session, user_id, trick_name, landed, job_id, awarded)
        _check_session_grind(session, user_id, session_id, job_id, awarded)
        _check_line_landed(session, user_id, job_id, landed, tricks_in_clip, awarded)
    except Exception:
        logger.warning(
            "Milestone check failed for user=%s job=%s",
            user_id,
            job_id,
            exc_info=True,
        )

    return awarded
