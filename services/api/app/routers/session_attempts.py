"""Session attempt log — server canonical store + offline-friendly sync."""

from __future__ import annotations

from datetime import datetime, timezone

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


def _owned_session(
    db: Session, session_id: str, user_id: str
) -> SkateSessionModel | None:
    row = db.get(SkateSessionModel, session_id)
    if row is None or row.deleted_at is not None:
        return None
    if row.user_id != user_id:
        return None
    return row


def _to_out(row: SessionAttemptModel) -> SessionAttemptOut:
    outcome = row.outcome if row.outcome in ("landed", "missed") else "missed"
    return SessionAttemptOut(
        id=row.id,
        session_id=row.session_id,
        trick_id=row.trick_id,
        canonical_name=row.canonical_name,
        outcome=outcome,  # type: ignore[arg-type]
        logged_at=iso_z(row.logged_at),
    )


@router.post("/session-attempts/sync", response_model=SessionAttemptSyncResponse)
def sync_session_attempts(
    body: SessionAttemptSyncRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionAttemptSyncResponse:
    """
    Idempotent batch upsert of client-logged attempts.

    Client ids are primary keys — replaying the same payload is a no-op update.
    """
    accepted: list[str] = []
    rejected: list[SessionAttemptRejected] = []
    session_cache: dict[str, SkateSessionModel | None] = {}

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

        if sid not in session_cache:
            session_cache[sid] = _owned_session(db, sid, user_id)
        sess = session_cache[sid]
        if sess is None:
            rejected.append(SessionAttemptRejected(id=aid, reason="session_not_found"))
            continue

        existing = db.get(SessionAttemptModel, aid)
        if existing is not None:
            if existing.user_id != user_id:
                rejected.append(SessionAttemptRejected(id=aid, reason="forbidden"))
                continue
            # Idempotent update of fields (same client id).
            existing.session_id = sid
            existing.trick_id = item.trick_id.strip()[:64]
            existing.canonical_name = item.canonical_name.strip()[:128]
            existing.outcome = item.outcome
            existing.logged_at = logged_at
            existing.deleted_at = None
            db.add(existing)
            accepted.append(aid)
            continue

        db.add(
            SessionAttemptModel(
                id=aid,
                user_id=user_id,
                session_id=sid,
                trick_id=item.trick_id.strip()[:64],
                canonical_name=item.canonical_name.strip()[:128],
                outcome=item.outcome,
                logged_at=logged_at,
            )
        )
        accepted.append(aid)

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
    return SessionAttemptListResponse(attempts=[_to_out(r) for r in rows])
