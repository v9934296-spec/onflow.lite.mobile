"""GET /api/v1/feed/stream — Step 10 SSE."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import get_engine
from app.services import feed_sse_hub
from app.services.feed_event_generator import find_session_recap_event
from app.services.feed_sse_hub import get_feed_sse_hub, reset_feed_sse_hub
from app.services.feed_sse_notify import notify_feed_event_created


@pytest.fixture(autouse=True)
def _fast_sse_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(feed_sse_hub, "HEARTBEAT_INTERVAL_SECONDS", 0.05)
    from app.routers import feed as feed_router

    monkeypatch.setattr(feed_router, "HEARTBEAT_INTERVAL_SECONDS", 0.05)


def test_feed_stream_requires_auth(client: TestClient) -> None:
    r = client.get("/api/v1/feed/stream", headers={"Accept": "text/event-stream"})
    assert r.status_code == 401


def test_feed_sse_hub_heartbeat_format() -> None:
    reset_feed_sse_hub()
    hub = get_feed_sse_hub()
    assert "event: heartbeat" in hub.heartbeat_message()


def test_notify_feed_event_created_publishes_to_hub(authed_client: TestClient) -> None:
    reset_feed_sse_hub()
    headers = authed_client.headers
    sess = authed_client.post(
        "/api/v1/sessions",
        json={"spot_label": "SSE Hub", "focus_trick": "heelflip"},
        headers=headers,
    )
    assert sess.status_code == 201, sess.text
    session_id = sess.json()["id"]
    ended = authed_client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"ended_at": "2026-06-05T12:00:00Z"},
        headers=headers,
    )
    assert ended.status_code == 200, ended.text

    hub = get_feed_sse_hub()
    q = hub.subscribe("test-user-001")
    with Session(get_engine()) as db:
        row = find_session_recap_event(
            db, user_id="test-user-001", session_id=session_id
        )
        assert row is not None
        notify_feed_event_created(db, row)

    message = q.get(timeout=1.0)
    assert "event: feed_event" in message
    assert "session_recap" in message


def test_end_session_triggers_sse_notify(authed_client: TestClient) -> None:
    reset_feed_sse_hub()
    headers = authed_client.headers
    hub = get_feed_sse_hub()
    q = hub.subscribe("test-user-001")

    sess = authed_client.post(
        "/api/v1/sessions",
        json={"spot_label": "SSE End", "focus_trick": "heelflip"},
        headers=headers,
    )
    assert sess.status_code == 201, sess.text
    session_id = sess.json()["id"]
    ended = authed_client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"ended_at": "2026-06-05T12:30:00Z"},
        headers=headers,
    )
    assert ended.status_code == 200, ended.text

    message = q.get(timeout=1.0)
    assert "session_recap" in message
