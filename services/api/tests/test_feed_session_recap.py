"""Feed session_recap generation and owner feed listing (Step 5C)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.database import get_engine
from app.models import FeedEventModel
from app.services.feed_event_generator import (
    find_session_recap_event,
    generate_session_recap_feed_event,
)


def _create_session(client: TestClient, headers: dict[str, str]) -> dict:
    r = client.post(
        "/api/v1/sessions",
        json={"spot_label": "Fremont Skatepark", "focus_trick": "kickflip"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_end_session_creates_session_recap_feed_event(authed_client: TestClient) -> None:
    headers = authed_client.headers
    sess = _create_session(authed_client, headers)
    ended = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    r = authed_client.patch(
        f"/api/v1/sessions/{sess['id']}",
        json={"ended_at": ended},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    with Session(get_engine()) as db:
        event = find_session_recap_event(
            db, user_id="test-user-001", session_id=sess["id"]
        )
        assert event is not None
        assert event.event_type == "session_recap"
        assert event.propagation_status == "propagated"

    feed = authed_client.get("/api/v1/feed", headers=headers)
    assert feed.status_code == 200, feed.text
    body = feed.json()
    recap_items = [i for i in body["items"] if i["event_type"] == "session_recap"]
    assert recap_items
    assert recap_items[0]["payload"].get("session_id") == sess["id"]
    assert recap_items[0]["payload"]["spot_label"] == "Fremont Skatepark"
    assert recap_items[0]["payload"]["focus_trick"] == "kickflip"


def test_end_session_feed_generation_is_idempotent(authed_client: TestClient) -> None:
    headers = authed_client.headers
    sess = _create_session(authed_client, headers)
    ended = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    patch_url = f"/api/v1/sessions/{sess['id']}"
    for _ in range(2):
        r = authed_client.patch(patch_url, json={"ended_at": ended}, headers=headers)
        assert r.status_code == 200, r.text

    with Session(get_engine()) as db:
        rows = list(
            db.exec(
                select(FeedEventModel).where(
                    FeedEventModel.user_id == "test-user-001",
                    FeedEventModel.skate_session_id == sess["id"],
                    FeedEventModel.event_type == "session_recap",
                )
            )
        )
        assert len(rows) == 1


def test_db_unique_guard_blocks_duplicate_recap(authed_client: TestClient) -> None:
    """Direct DB-layer guard: a second generate call cannot insert a duplicate."""
    headers = authed_client.headers
    sess = _create_session(authed_client, headers)
    ended = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    r = authed_client.patch(
        f"/api/v1/sessions/{sess['id']}", json={"ended_at": ended}, headers=headers
    )
    assert r.status_code == 200, r.text

    with Session(get_engine()) as db:
        first = generate_session_recap_feed_event(
            db, sess["id"], user_id="test-user-001"
        )
        second = generate_session_recap_feed_event(
            db, sess["id"], user_id="test-user-001"
        )
        assert first is not None and second is not None
        assert first.id == second.id
        rows = list(
            db.exec(
                select(FeedEventModel).where(
                    FeedEventModel.skate_session_id == sess["id"],
                    FeedEventModel.event_type == "session_recap",
                )
            )
        )
        assert len(rows) == 1


def test_feed_returns_owner_events_only(client: TestClient) -> None:
    """A user's feed never includes another user's session_recap events."""
    owner = {"Authorization": "Bearer dev:owner-aaa"}
    other = {"Authorization": "Bearer dev:other-bbb"}

    owner_sess = _create_session(client, owner)
    other_sess = _create_session(client, other)
    ended = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    assert (
        client.patch(
            f"/api/v1/sessions/{owner_sess['id']}", json={"ended_at": ended}, headers=owner
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/sessions/{other_sess['id']}", json={"ended_at": ended}, headers=other
        ).status_code
        == 200
    )

    feed = client.get("/api/v1/feed", headers=owner)
    assert feed.status_code == 200, feed.text
    sessions_in_feed = {
        i["payload"].get("session_id") for i in feed.json()["items"]
    }
    assert owner_sess["id"] in sessions_in_feed
    assert other_sess["id"] not in sessions_in_feed


def test_feed_sorted_newest_first(authed_client: TestClient) -> None:
    headers = authed_client.headers
    ended = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ids = []
    for _ in range(3):
        sess = _create_session(authed_client, headers)
        authed_client.patch(
            f"/api/v1/sessions/{sess['id']}", json={"ended_at": ended}, headers=headers
        )
        ids.append(sess["id"])

    items = authed_client.get("/api/v1/feed", headers=headers).json()["items"]
    times = [i["generated_at"] for i in items]
    assert times == sorted(times, reverse=True)


def test_empty_feed_returns_stable_shape(client: TestClient) -> None:
    headers = {"Authorization": "Bearer dev:empty-user-ccc"}
    body = client.get("/api/v1/feed", headers=headers).json()
    assert body["items"] == []
    assert body["next_cursor"] is None
    assert body["lifecycle_stage"] == "stage_a"


def test_recap_payload_has_card_fields(authed_client: TestClient) -> None:
    headers = authed_client.headers
    sess = _create_session(authed_client, headers)
    ended = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    authed_client.patch(
        f"/api/v1/sessions/{sess['id']}", json={"ended_at": ended}, headers=headers
    )
    item = [
        i
        for i in authed_client.get("/api/v1/feed", headers=headers).json()["items"]
        if i["event_type"] == "session_recap"
    ][0]
    assert item["event_version"] == "feed_1.0.0"
    assert item["user"]["user_id"] == "test-user-001"
    payload = item["payload"]
    for key in (
        "session_id",
        "spot_label",
        "clip_count",
        "attempt_count",
        "focus_trick",
        "completed_at",
    ):
        assert key in payload, f"missing payload key: {key}"
