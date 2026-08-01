"""Feed endpoints (Step 5C — owner feed, session_recap events)."""
from __future__ import annotations

import asyncio
import base64
import json
import queue
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, func, select

from app.core.auth import (
    get_current_user,
    get_current_user_sse,
    issue_sse_access_token,
)
from app.core.database import get_db
from app.core.tiers import normalize_tier
from app.models import FeedEventModel, SkateSessionModel, UserModel
from app.schemas.feed import (
    FeedEventItemResponse,
    FeedListResponse,
    FeedUserResponse,
    ReactionBucketResponse,
    ReactionsSummaryResponse,
)
from app.services.clip_upload import iso_z
from app.services.feed_sse_hub import HEARTBEAT_INTERVAL_SECONDS, get_feed_sse_hub

router = APIRouter(prefix="/api/v1", tags=["feed"])

_EMPTY_REACTIONS = ReactionsSummaryResponse(
    fire=ReactionBucketResponse(),
    saw_it=ReactionBucketResponse(),
    same_battle=ReactionBucketResponse(),
    progression=ReactionBucketResponse(),
)


def _tier_for_feed(raw: str | None) -> str:
    t = normalize_tier(raw)
    if t == "pro":
        return "pro"
    return "flow"


def _feed_user(db: Session, user_id: str) -> FeedUserResponse:
    u = db.get(UserModel, user_id)
    if u is None:
        return FeedUserResponse(
            user_id=user_id,
            username=user_id[:12],
            tag_name="Skater",
            profile_photo_url=None,
            tier="flow",
        )
    local = (u.email or "").split("@")[0].strip() or user_id[:12]
    tag = local.replace(".", " ").replace("_", " ").title() or "Skater"
    return FeedUserResponse(
        user_id=u.id,
        username=local,
        tag_name=tag,
        profile_photo_url=u.profile_image_url,
        tier=_tier_for_feed(u.tier),
    )


def _lifecycle_stage(db: Session, user_id: str) -> str:
    session_count = int(
        db.exec(
            select(func.count(SkateSessionModel.id)).where(
                SkateSessionModel.user_id == user_id,
                SkateSessionModel.deleted_at.is_(None),  # type: ignore[union-attr]
            )
        ).one()
    )
    if session_count == 0:
        return "stage_a"
    # Friend graph not shipped — solo progression uses stage_b until social ships.
    return "stage_b"


def _encode_cursor(generated_at: datetime, event_id: str) -> str:
    payload = {"g": iso_z(generated_at), "id": event_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    try:
        raw = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        g = raw.get("g")
        eid = raw.get("id")
        if not isinstance(g, str) or not isinstance(eid, str):
            return None
        ts = datetime.fromisoformat(g.replace("Z", "+00:00"))
        return ts, eid
    except Exception:
        return None


def _event_to_item(row: FeedEventModel, user: FeedUserResponse) -> FeedEventItemResponse:
    payload = json.loads(row.payload_json or "{}")
    if not isinstance(payload, dict):
        payload = {}
    return FeedEventItemResponse(
        id=row.id,
        user=user,
        event_type=row.event_type,
        event_version=row.event_version,
        payload=payload,
        generated_at=iso_z(row.generated_at),
        reactions_summary=_EMPTY_REACTIONS,
    )


@router.get("/feed", response_model=FeedListResponse)
def list_feed(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> FeedListResponse:
    """V1: returns the signed-in user's own propagated feed events."""
    stmt = (
        select(FeedEventModel)
        .where(
            FeedEventModel.user_id == user_id,
            FeedEventModel.propagation_status == "propagated",
            FeedEventModel.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(FeedEventModel.generated_at.desc(), FeedEventModel.id.desc())
    )
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            cur_at, cur_id = decoded
            stmt = stmt.where(
                (FeedEventModel.generated_at < cur_at)
                | (
                    (FeedEventModel.generated_at == cur_at)
                    & (FeedEventModel.id < cur_id)
                )
            )

    rows = list(db.exec(stmt.limit(limit + 1)))
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = _encode_cursor(last.generated_at, last.id)

    # Owner feed: every row belongs to the signed-in user, so resolve the user once
    # instead of once per row (was an N+1 over the users table).
    feed_user = _feed_user(db, user_id)
    items = [_event_to_item(r, feed_user) for r in rows]
    return FeedListResponse(
        items=items,
        next_cursor=next_cursor,
        lifecycle_stage=_lifecycle_stage(db, user_id),
    )


async def _feed_stream_generator(
    user_id: str,
    subscriber_q: queue.Queue[str],
    request: Request,
):
    hub = get_feed_sse_hub()
    try:
        while not await request.is_disconnected():
            try:
                message = await asyncio.to_thread(subscriber_q.get, False)
                yield message
            except queue.Empty:
                yield hub.heartbeat_message()
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
    finally:
        hub.unsubscribe(user_id, subscriber_q)


def _backfill_since_event_id(
    db: Session, user_id: str, last_event_id: str
) -> list[FeedEventItemResponse]:
    anchor = db.get(FeedEventModel, last_event_id)
    if anchor is None or anchor.user_id != user_id:
        return []
    stmt = (
        select(FeedEventModel)
        .where(
            FeedEventModel.user_id == user_id,
            FeedEventModel.propagation_status == "propagated",
            FeedEventModel.deleted_at.is_(None),  # type: ignore[union-attr]
            FeedEventModel.generated_at > anchor.generated_at,
        )
        .order_by(FeedEventModel.generated_at.asc(), FeedEventModel.id.asc())
    )
    user = _feed_user(db, user_id)
    return [_event_to_item(row, user) for row in db.exec(stmt)]


@router.post("/feed/sse-ticket")
def issue_feed_sse_ticket(
    user_id: str = Depends(get_current_user),
) -> dict[str, object]:
    """Mint a short-lived SSE ticket for EventSource ``?token=`` (not the session JWT)."""
    ttl = 300
    return {
        "token": issue_sse_access_token(user_id, ttl_seconds=ttl),
        "expires_in": ttl,
        "token_type": "sse",
    }


@router.get("/feed/stream")
async def feed_stream(
    request: Request,
    user_id: str = Depends(get_current_user_sse),
    db: Session = Depends(get_db),
    last_event_id: str | None = Query(default=None, alias="lastEventId"),
) -> StreamingResponse:
    """SSE stream of feed updates for the signed-in user (contracts §8.2)."""
    hub = get_feed_sse_hub()
    subscriber_q = hub.subscribe(user_id)
    backfill = (
        _backfill_since_event_id(db, user_id, last_event_id)
        if last_event_id
        else []
    )

    async def stream():
        for item in backfill:
            if await request.is_disconnected():
                return
            yield hub.format_message(
                event_name="feed_event",
                data=item.model_dump(mode="json"),
                event_id=item.id,
            )
        try:
            async for chunk in _feed_stream_generator(user_id, subscriber_q, request):
                if await request.is_disconnected():
                    break
                yield chunk
        finally:
            hub.unsubscribe(user_id, subscriber_q)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
