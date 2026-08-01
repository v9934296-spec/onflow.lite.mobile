"""GET /api/v1/progression/timeline — personal session history (Step 5F).

Ordering is newest-first by ended_at (tie-break id desc).
Only ended, non-deleted, owner sessions appear. Offset pagination (page/page_size).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import get_engine
from app.models import ClipModel, SkateSessionModel

BASE = datetime(2026, 6, 1, 18, 0, 0, tzinfo=timezone.utc)


def _insert_session(
    user_id: str,
    *,
    started: datetime,
    ended: datetime | None,
    spot: str | None = "Spot",
    focus: str | None = "kickflip",
) -> str:
    sid = str(uuid.uuid4())
    with Session(get_engine()) as db:
        db.add(
            SkateSessionModel(
                id=sid,
                user_id=user_id,
                spot_label=spot,
                focus_trick=focus,
                started_at=started,
                ended_at=ended,
            )
        )
        db.commit()
    return sid


def _insert_clip(
    session_id: str,
    user_id: str,
    *,
    pte: int | None = None,
    thumbnail_url: str | None = None,
    created_at: datetime | None = None,
) -> str:
    cid = str(uuid.uuid4())
    with Session(get_engine()) as db:
        db.add(
            ClipModel(
                id=cid,
                user_id=user_id,
                session_id=session_id,
                storage_key=f"clips/{cid}.mp4",
                thumbnail_url=thumbnail_url,
                pte_rating=pte,
                upload_status="ready",
                created_at=created_at or datetime.now(timezone.utc),
            )
        )
        db.commit()
    return cid


def test_owner_only_sessions(client: TestClient) -> None:
    owner = {"Authorization": "Bearer dev:owner-aaa"}
    other = {"Authorization": "Bearer dev:other-bbb"}
    mine = _insert_session("owner-aaa", started=BASE, ended=BASE + timedelta(minutes=30))
    theirs = _insert_session("other-bbb", started=BASE, ended=BASE + timedelta(minutes=30))

    body = client.get("/api/v1/progression/timeline", headers=owner).json()
    ids = {i["session_id"] for i in body["items"]}
    assert mine in ids
    assert theirs not in ids


def test_only_ended_sessions_appear(authed_client: TestClient) -> None:
    ended = _insert_session("test-user-001", started=BASE, ended=BASE + timedelta(minutes=20))
    active = _insert_session("test-user-001", started=BASE, ended=None)
    body = authed_client.get("/api/v1/progression/timeline").json()
    ids = {i["session_id"] for i in body["items"]}
    assert ended in ids
    assert active not in ids


def test_newest_first_ordering(authed_client: TestClient) -> None:
    older = _insert_session("test-user-001", started=BASE, ended=BASE + timedelta(minutes=10))
    newer = _insert_session(
        "test-user-001", started=BASE, ended=BASE + timedelta(hours=2)
    )
    items = authed_client.get("/api/v1/progression/timeline").json()["items"]
    ids = [i["session_id"] for i in items]
    assert ids.index(newer) < ids.index(older)


def test_pagination(authed_client: TestClient) -> None:
    for n in range(5):
        _insert_session(
            "test-user-001", started=BASE, ended=BASE + timedelta(minutes=n)
        )
    page1 = authed_client.get(
        "/api/v1/progression/timeline", params={"page": 1, "page_size": 2}
    ).json()
    assert len(page1["items"]) == 2
    assert page1["page"] == 1
    assert page1["page_size"] == 2
    assert page1["has_more"] is True

    page3 = authed_client.get(
        "/api/v1/progression/timeline", params={"page": 3, "page_size": 2}
    ).json()
    assert len(page3["items"]) == 1
    assert page3["has_more"] is False

    # No overlap between pages.
    ids1 = {i["session_id"] for i in page1["items"]}
    page2 = authed_client.get(
        "/api/v1/progression/timeline", params={"page": 2, "page_size": 2}
    ).json()
    ids2 = {i["session_id"] for i in page2["items"]}
    assert ids1.isdisjoint(ids2)


def test_empty_timeline_stable(client: TestClient) -> None:
    body = client.get(
        "/api/v1/progression/timeline",
        headers={"Authorization": "Bearer dev:empty-ccc"},
    ).json()
    assert body["items"] == []
    assert body["page"] == 1
    assert body["has_more"] is False


def test_missing_optional_fields_safe(authed_client: TestClient) -> None:
    # Session with no spot/focus and no clips.
    sid = _insert_session(
        "test-user-001", started=BASE, ended=BASE + timedelta(minutes=15), spot=None, focus=None
    )
    item = next(
        i
        for i in authed_client.get("/api/v1/progression/timeline").json()["items"]
        if i["session_id"] == sid
    )
    assert item["spot"] is None
    assert item["focus_trick"] is None
    assert item["clips_count"] == 0
    assert item["attempt_count"] == 0
    assert item["best_pte_score"] is None
    assert item["thumbnail_url"] is None
    assert item["duration_seconds"] == 900


def test_preview_metrics_aggregate(authed_client: TestClient) -> None:
    sid = _insert_session("test-user-001", started=BASE, ended=BASE + timedelta(minutes=30))
    _insert_clip(sid, "test-user-001", pte=5, created_at=BASE + timedelta(minutes=1))
    _insert_clip(
        sid,
        "test-user-001",
        pte=9,
        thumbnail_url="https://cdn/newest.jpg",
        created_at=BASE + timedelta(minutes=9),
    )
    item = next(
        i
        for i in authed_client.get("/api/v1/progression/timeline").json()["items"]
        if i["session_id"] == sid
    )
    assert item["clips_count"] == 2
    assert item["attempt_count"] == 0
    assert item["best_pte_score"] == 9
    assert item["thumbnail_url"] == "https://cdn/newest.jpg"


def test_timeline_attempt_count_from_synced_attempts(authed_client: TestClient) -> None:
    sid = _insert_session("test-user-001", started=BASE, ended=BASE + timedelta(minutes=20))
    _insert_clip(sid, "test-user-001", pte=4, created_at=BASE + timedelta(minutes=1))
    sync = authed_client.post(
        "/api/v1/session-attempts/sync",
        json={
            "attempts": [
                {
                    "id": "tl-a1",
                    "session_id": sid,
                    "trick_id": "kickflip",
                    "canonical_name": "Kickflip",
                    "outcome": "landed",
                    "logged_at": "2026-06-01T18:05:00Z",
                },
                {
                    "id": "tl-a2",
                    "session_id": sid,
                    "trick_id": "kickflip",
                    "canonical_name": "Kickflip",
                    "outcome": "missed",
                    "logged_at": "2026-06-01T18:06:00Z",
                },
                {
                    "id": "tl-a3",
                    "session_id": sid,
                    "trick_id": "heelflip",
                    "canonical_name": "Heelflip",
                    "outcome": "landed",
                    "logged_at": "2026-06-01T18:07:00Z",
                },
            ]
        },
    )
    assert sync.status_code == 200, sync.text
    item = next(
        i
        for i in authed_client.get("/api/v1/progression/timeline").json()["items"]
        if i["session_id"] == sid
    )
    assert item["clips_count"] == 1
    assert item["attempt_count"] == 3


def test_large_history_remains_paginated(authed_client: TestClient) -> None:
    for n in range(25):
        _insert_session(
            "test-user-001", started=BASE, ended=BASE + timedelta(minutes=n)
        )
    body = authed_client.get(
        "/api/v1/progression/timeline", params={"page": 1, "page_size": 20}
    ).json()
    assert len(body["items"]) == 20
    assert body["has_more"] is True
