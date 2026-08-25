"""Session attempt log — server canonical store + offline-friendly sync.

The manual outcome is the authoritative record of what the skater actually did.
Sync is therefore an **immutable replay contract**, not an upsert: replaying a
row is accepted only when it is byte-for-byte the same decision. Any changed
field is rejected so a stale queued row from a phone that was offline for two
days can never rewrite history, move an attempt between sessions, or resurrect
a deleted one.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import SessionAttemptModel, SkateSessionModel
from app.schemas.session_attempts import (
    SessionAttemptListResponse,
    SessionAttemptOut,
    SessionAttemptRejected,
    SessionAttemptSyncRequest,
    SessionAttemptSyncResponse,
)
from app.services.clip_upload import iso_z

router = APIRouter(prefix="/api/v1", tags=["session-attempts"])

logger = structlog.get_logger(__name__)

VALID_OUTCOMES = ("landed", "missed")

TRICK_ID_MAX = 64
CANONICAL_NAME_MAX = 128


def _parse_logged_at(raw: str) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _as_utc(dt: datetime) -> datetime:
    """Storage drops the offset, so a round-tripped value comes back naive UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _owned_session(
    db: Session, session_id: str, user_id: str
) -> SkateSessionModel | None:
    row = db.get(SkateSessionModel, session_id)
    if row is None or row.deleted_at is not None:
        return None
    if row.user_id != user_id:
        return None
    return row


def _to_out(row: SessionAttemptModel) -> SessionAttemptOut | None:
    """Maps a stored row to the wire shape, or ``None`` when it cannot be trusted.

    An unrecognized stored outcome is **not** downgraded to ``missed``. Guessing
    here would silently rewrite the one record the skater is the authority on, so
    the row is omitted and logged for investigation instead.
    """
    if row.outcome not in VALID_OUTCOMES:
        logger.error(
            "session_attempt_unknown_outcome",
            attempt_id=row.id,
            session_id=row.session_id,
            stored_outcome=row.outcome,
        )
        return None
    return SessionAttemptOut(
        id=row.id,
        session_id=row.session_id,
        trick_id=row.trick_id,
        canonical_name=row.canonical_name,
        outcome=row.outcome,  # type: ignore[arg-type]
        logged_at=iso_z(row.logged_at),
    )


def _identity_of_stored(row: SessionAttemptModel) -> tuple[str, str, str, str, datetime]:
    return (
        row.session_id,
        row.trick_id,
        row.canonical_name,
        row.outcome,
        _as_utc(row.logged_at),
    )


@router.post("/session-attempts/sync", response_model=SessionAttemptSyncResponse)
def sync_session_attempts(
    body: SessionAttemptSyncRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionAttemptSyncResponse:
    """Immutable batch sync of client-logged attempts.

    Client ids are primary keys. Replaying an identical payload is accepted and
    changes nothing; replaying a *different* payload under an existing id is
    rejected. Nothing in this endpoint mutates an existing attempt.
    """
    accepted: list[str] = []
    rejected: list[SessionAttemptRejected] = []
    session_cache: dict[str, SkateSessionModel | None] = {}
    pending: list[SessionAttemptModel] = []

    # Pass 1: normalize, and settle intra-batch duplicates before touching the
    # database. A batch carrying one id twice with different content is the same
    # contradiction as a cross-request replay, and resolving it up front keeps
    # the result independent of row order — an id is never both accepted and
    # rejected in one response.
    parsed: dict[str, tuple[str, str, str, str, datetime]] = {}
    order: list[str] = []
    conflicted: list[str] = []

    for item in body.attempts:
        aid = item.id.strip()
        sid = item.session_id.strip()
        if not aid or not sid:
            rejected.append(SessionAttemptRejected(id=item.id, reason="missing_id"))
            continue

        logged_at = _parse_logged_at(item.logged_at)
        if logged_at is None:
            rejected.append(SessionAttemptRejected(id=aid, reason="invalid_logged_at"))
            continue

        incoming = (
            sid,
            item.trick_id.strip()[:TRICK_ID_MAX],
            item.canonical_name.strip()[:CANONICAL_NAME_MAX],
            item.outcome,
            _as_utc(logged_at),
        )

        previous = parsed.get(aid)
        if previous is None:
            parsed[aid] = incoming
            order.append(aid)
        elif previous != incoming and aid not in conflicted:
            conflicted.append(aid)

    for aid in conflicted:
        logger.warning(
            "session_attempt_batch_duplicate_conflict", attempt_id=aid, user_id=user_id
        )
        rejected.append(SessionAttemptRejected(id=aid, reason="duplicate_in_batch"))

    # Pass 2: apply. Nothing here mutates an existing attempt.
    for aid in order:
        if aid in conflicted:
            continue
        incoming = parsed[aid]
        sid = incoming[0]

        if sid not in session_cache:
            session_cache[sid] = _owned_session(db, sid, user_id)
        if session_cache[sid] is None:
            rejected.append(SessionAttemptRejected(id=aid, reason="session_not_found"))
            continue

        existing = db.get(SessionAttemptModel, aid)
        if existing is not None:
            if existing.user_id != user_id:
                rejected.append(SessionAttemptRejected(id=aid, reason="forbidden"))
                continue
            if existing.deleted_at is not None:
                # A deleted attempt stays deleted. Clearing deleted_at here is
                # how a stale outbox row resurrects a record the skater removed.
                rejected.append(
                    SessionAttemptRejected(id=aid, reason="attempt_deleted")
                )
                continue

            if _identity_of_stored(existing) == incoming:
                # Accepted replay. Deliberately no writes.
                accepted.append(aid)
                continue

            reason = (
                "session_immutable"
                if existing.session_id != incoming[0]
                else "outcome_immutable"
                if existing.outcome != incoming[3]
                else "attempt_immutable"
            )
            logger.warning(
                "session_attempt_replay_conflict",
                attempt_id=aid,
                reason=reason,
                user_id=user_id,
            )
            rejected.append(SessionAttemptRejected(id=aid, reason=reason))
            continue

        pending.append(
            SessionAttemptModel(
                id=aid,
                user_id=user_id,
                session_id=sid,
                trick_id=incoming[1],
                canonical_name=incoming[2],
                outcome=incoming[3],
                logged_at=incoming[4],
            )
        )
        accepted.append(aid)

    for row in pending:
        db.add(row)
    db.commit()
    return SessionAttemptSyncResponse(accepted=accepted, rejected=rejected)


@router.get(
    "/sessions/{session_id}/attempts",
    response_model=SessionAttemptListResponse,
)
def list_session_attempts(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionAttemptListResponse:
    sess = _owned_session(db, session_id, user_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    rows = list(
        db.exec(
            select(SessionAttemptModel)
            .where(
                SessionAttemptModel.user_id == user_id,
                SessionAttemptModel.session_id == session_id,
                SessionAttemptModel.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            .order_by(SessionAttemptModel.logged_at.asc())
        )
    )
    mapped = [out for out in (_to_out(r) for r in rows) if out is not None]
    return SessionAttemptListResponse(attempts=mapped)
