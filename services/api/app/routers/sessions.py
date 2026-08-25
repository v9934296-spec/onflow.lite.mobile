"""V1 skating session CRUD endpoints (contracts §3)."""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import update as sa_update
from sqlmodel import Session, func, select

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.feature_gates import tier_has_feature
from app.core.tiers import normalize_tier
from app.models import ClipModel, SessionAttemptModel, SkateSessionModel
from app.schemas.sessions import (
    SessionCreate,
    SessionListItem,
    SessionListResponse,
    SessionParticipantAdd,
    SessionRecapDetailResponse,
    SessionResponse,
    SessionUpdate,
)
from app.services.clip_upload import as_utc, iso_z
from app.services.feed_event_generator import generate_session_recap_feed_event
from app.services.session_recap import build_session_recap_detail
from app.services.trick_registry import normalize_trick_name

router = APIRouter(prefix="/api/v1", tags=["sessions"])

_PARTICIPANTS_NOT_IMPLEMENTED = (
    "Session participants are not implemented until friendships ship (Step 5B.1 stub)."
)

_TRIAL_ENDED_SESSION_MESSAGE = (
    "Your free trial has ended. Subscribe to Pro or grab a Re-Up pack to start recording sessions."
)


def _require_record_session_feature(request: Request, user_id: str) -> None:
    db = request.app.state.db
    tier = normalize_tier(db.get_user_tier(user_id))
    if not tier_has_feature(tier, "record_session"):
        raise HTTPException(status_code=403, detail=_TRIAL_ENDED_SESSION_MESSAGE)


def _new_session_id() -> str:
    return str(uuid.uuid4())


def _active_session(
    db: Session, session_id: str, *, for_user: str | None = None
) -> SkateSessionModel | None:
    row = db.get(SkateSessionModel, session_id)
    if row is None or row.deleted_at is not None:
        return None
    if for_user is not None and row.user_id != for_user:
        return None
    return row


def _clip_counts(db: Session, session_id: str) -> tuple[int, int]:
    stmt = select(func.count(ClipModel.id)).where(
        ClipModel.session_id == session_id,
        ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    clip_count = int(db.exec(stmt).one())
    attempt_stmt = select(func.count(SessionAttemptModel.id)).where(
        SessionAttemptModel.session_id == session_id,
        SessionAttemptModel.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    attempt_count = int(db.exec(attempt_stmt).one())
    return clip_count, attempt_count


def _session_list_aggregates(
    db: Session, session_ids: list[str]
) -> tuple[dict[str, int], dict[str, int], dict[str, list[str]], dict[str, str]]:
    """Batch per-session list metrics (avoids N+1 over clips/attempts).

    Returns (
        clip_count_by_session,
        attempt_count_by_session,
        tricks_by_session,
        latest_thumbnail_by_session,
    ).
    """
    if not session_ids:
        return {}, {}, {}, {}

    count_rows = db.exec(
        select(ClipModel.session_id, func.count(ClipModel.id))
        .where(
            ClipModel.session_id.in_(session_ids),  # type: ignore[union-attr]
            ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .group_by(ClipModel.session_id)
    ).all()
    counts = {sid: int(c) for sid, c in count_rows}

    attempt_rows = db.exec(
        select(SessionAttemptModel.session_id, func.count(SessionAttemptModel.id))
        .where(
            SessionAttemptModel.session_id.in_(session_ids),  # type: ignore[union-attr]
            SessionAttemptModel.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .group_by(SessionAttemptModel.session_id)
    ).all()
    attempt_counts = {sid: int(c) for sid, c in attempt_rows}

    trick_rows = db.exec(
        select(ClipModel.session_id, ClipModel.trick_id)
        .where(
            ClipModel.session_id.in_(session_ids),  # type: ignore[union-attr]
            ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
            ClipModel.trick_id.is_not(None),  # type: ignore[union-attr]
        )
        .distinct()
    ).all()
    tricks: dict[str, list[str]] = {}
    for sid, trick in trick_rows:
        if trick:
            tricks.setdefault(sid, []).append(trick)

    thumb_rows = db.exec(
        select(ClipModel.session_id, ClipModel.thumbnail_url)
        .where(
            ClipModel.session_id.in_(session_ids),  # type: ignore[union-attr]
            ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
            ClipModel.thumbnail_url.is_not(None),  # type: ignore[union-attr]
        )
        .order_by(ClipModel.created_at.desc())
    ).all()
    thumbs: dict[str, str] = {}
    for sid, url in thumb_rows:
        if url and sid not in thumbs:
            thumbs[sid] = url

    return counts, attempt_counts, tricks, thumbs


def _session_to_response(
    row: SkateSessionModel,
    db: Session,
    *,
    include_clips: bool = False,
) -> SessionResponse:
    clip_count, attempt_count = _clip_counts(db, row.id)
    clips_payload = None
    if include_clips:
        stmt = (
            select(ClipModel)
            .where(
                ClipModel.session_id == row.id,
                ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            .order_by(ClipModel.created_at.desc())
        )
        clip_rows = list(db.exec(stmt))
        clips_payload = [
            {
                "id": c.id,
                "trick_id": c.trick_id,
                "trick_display": normalize_trick_name(c.trick_id) if c.trick_id else None,
                "thumbnail_url": c.thumbnail_url,
                "landed": c.landed,
                "pte_rating": c.pte_rating,
                "created_at": iso_z(c.created_at),
                "is_first_land": c.is_first_land,
            }
            for c in clip_rows
        ]
    return SessionResponse(
        id=row.id,
        user_id=row.user_id,
        spot_label=row.spot_label,
        focus_trick=row.focus_trick,
        notes=row.notes,
        started_at=iso_z(row.started_at),
        ended_at=iso_z(row.ended_at) if row.ended_at else None,
        breakthrough_note=row.breakthrough_note,
        clip_count=clip_count,
        attempt_count=attempt_count,
        participants=[],
        created_at=iso_z(row.created_at),
        updated_at=iso_z(row.updated_at),
        clips=clips_payload,
    )


def _encode_cursor(started_at: datetime, session_id: str) -> str:
    payload = {"started_at": iso_z(started_at), "id": session_id}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(raw)
        started = datetime.fromisoformat(str(data["started_at"]).replace("Z", "+00:00"))
        return started, str(data["id"])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor.") from exc


@router.post("/sessions", status_code=201, response_model=SessionResponse)
def create_session(
    body: SessionCreate,
    request: Request,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    _require_record_session_feature(request, user_id)
    now = datetime.now(timezone.utc)
    started = body.started_at or now
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    row = SkateSessionModel(
        id=_new_session_id(),
        user_id=user_id,
        spot_label=body.spot_label,
        focus_trick=body.focus_trick,
        notes=body.notes,
        started_at=started,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _session_to_response(row, db)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    row = db.get(SkateSessionModel, session_id)
    if row is None or row.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if row.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found.")
    return _session_to_response(row, db, include_clips=True)


@router.get("/sessions/{session_id}/recap", response_model=SessionRecapDetailResponse)
def get_session_recap(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionRecapDetailResponse:
    """Aggregated progression recap for the session detail view (Step 5E).

    Owner-scoped. Returns the same safe 404 used elsewhere for a missing,
    soft-deleted, or non-owned session (no ownership leak).
    """
    recap = build_session_recap_detail(db, session_id, user_id=user_id)
    if recap is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return recap


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str,
    body: SessionUpdate,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    row = _active_session(db, session_id, for_user=user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    data = body.model_dump(exclude_unset=True)
    now = datetime.now(timezone.utc)

    incoming_end: datetime | None = None
    wants_end = False
    if "ended_at" in data:
        incoming = data.pop("ended_at")
        if incoming is not None:
            incoming_end = as_utc(incoming)
            wants_end = True

    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = now
    db.add(row)
    db.flush()

    transitioned = False
    if wants_end:
        # First write wins in the database, not in a prior in-memory snapshot.
        result = db.execute(
            sa_update(SkateSessionModel)
            .where(
                SkateSessionModel.id == session_id,
                SkateSessionModel.user_id == user_id,
                SkateSessionModel.ended_at.is_(None),
                SkateSessionModel.deleted_at.is_(None),
            )
            .values(ended_at=incoming_end, updated_at=now)
        )
        transitioned = int(result.rowcount or 0) == 1
        db.refresh(row)

    db.commit()
    db.refresh(row)
    if transitioned:
        generate_session_recap_feed_event(db, session_id, user_id=user_id)
    return _session_to_response(row, db)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    row = _active_session(db, session_id, for_user=user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    now = datetime.now(timezone.utc)
    row.deleted_at = now
    row.updated_at = now
    db.add(row)
    db.commit()
    return Response(status_code=204)


@router.get("/me/sessions", response_model=SessionListResponse)
def list_my_sessions(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> SessionListResponse:
    stmt = (
        select(SkateSessionModel)
        .where(
            SkateSessionModel.user_id == user_id,
            SkateSessionModel.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(SkateSessionModel.started_at.desc(), SkateSessionModel.id.desc())
    )
    if cursor:
        cur_started, cur_id = _decode_cursor(cursor)
        stmt = stmt.where(
            (SkateSessionModel.started_at < cur_started)
            | (
                (SkateSessionModel.started_at == cur_started)
                & (SkateSessionModel.id < cur_id)
            )
        )
    rows = list(db.exec(stmt.limit(limit + 1)))
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.started_at, last.id)
        rows = rows[:limit]

    counts, attempt_counts, tricks_by_session, thumb_by_session = _session_list_aggregates(
        db, [row.id for row in rows]
    )
    items: list[SessionListItem] = []
    for row in rows:
        clip_count = counts.get(row.id, 0)
        items.append(
            SessionListItem(
                id=row.id,
                spot_label=row.spot_label,
                focus_trick=row.focus_trick,
                started_at=iso_z(row.started_at),
                ended_at=iso_z(row.ended_at) if row.ended_at else None,
                clip_count=clip_count,
                attempt_count=attempt_counts.get(row.id, 0),
                breakthrough_note=row.breakthrough_note,
                tricks_attempted=tricks_by_session.get(row.id, []),
                preview_thumbnail_url=thumb_by_session.get(row.id),
            )
        )
    return SessionListResponse(items=items, next_cursor=next_cursor)


@router.post("/sessions/{session_id}/participants", status_code=501)
def add_participant(
    session_id: str,
    _body: SessionParticipantAdd,
    _user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    raise HTTPException(status_code=501, detail=_PARTICIPANTS_NOT_IMPLEMENTED)


@router.delete("/sessions/{session_id}/participants/{participant_user_id}", status_code=501)
def remove_participant(
    session_id: str,
    participant_user_id: str,
    _user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    raise HTTPException(status_code=501, detail=_PARTICIPANTS_NOT_IMPLEMENTED)
