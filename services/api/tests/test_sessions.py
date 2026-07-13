"""V1 skating session endpoints (Step 5B.1)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import get_engine
from app.models import SkateSessionModel


def _create_session(
    client: TestClient,
    headers: dict[str, str],
    *,
    spot_label: str | None = None,
    focus_trick: str | None = None,
    notes: str | None = None,
) -> dict:
    payload: dict = {}
    if spot_label is not None:
        payload["spot_label"] = spot_label
    if focus_trick is not None:
        payload["focus_trick"] = focus_trick
    if notes is not None:
        payload["notes"] = notes
    r = client.post("/api/v1/sessions", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_session_with_all_fields(authed_client: TestClient) -> None:
    body = _create_session(
        authed_client,
        authed_client.headers,
        spot_label="Fremont",
        focus_trick="kickflip",
        notes="warm up",
    )
    assert body["spot_label"] == "Fremont"
    assert body["focus_trick"] == "kickflip"
    assert body["notes"] == "warm up"
    assert body["user_id"] == "test-user-001"
    assert body["ended_at"] is None
    assert body["clip_count"] == 0
    assert body["attempt_count"] == 0
    assert body["id"]


def test_create_session_minimal_fields(authed_client: TestClient) -> None:
    body = _create_session(authed_client, authed_client.headers)
    assert body["spot_label"] is None
    assert body["focus_trick"] is None
    assert body["notes"] is None
    assert body["started_at"]
    assert body["ended_at"] is None


def test_read_session_returns_owner_session(authed_client: TestClient) -> None:
    created = _create_session(authed_client, authed_client.headers, spot_label="Park")
    r = authed_client.get(f"/api/v1/sessions/{created['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == created["id"]
    assert data["clips"] == []


def test_read_session_404_for_other_user(client: TestClient, authed_client: TestClient) -> None:
    created = _create_session(authed_client, authed_client.headers)
    r = client.get(
        f"/api/v1/sessions/{created['id']}",
        headers={"Authorization": "Bearer dev:other-user-999"},
    )
    assert r.status_code == 404


def test_read_session_404_when_soft_deleted(authed_client: TestClient) -> None:
    created = _create_session(authed_client, authed_client.headers)
    dr = authed_client.delete(f"/api/v1/sessions/{created['id']}")
    assert dr.status_code == 204
    r = authed_client.get(f"/api/v1/sessions/{created['id']}")
    assert r.status_code == 404


def test_update_session_sets_ended_at(authed_client: TestClient) -> None:
    created = _create_session(authed_client, authed_client.headers)
    ended = "2026-05-28T15:30:00Z"
    r = authed_client.patch(
        f"/api/v1/sessions/{created['id']}",
        json={"ended_at": ended},
    )
    assert r.status_code == 200
    assert r.json()["ended_at"] == ended


def test_update_session_sets_breakthrough_note(authed_client: TestClient) -> None:
    created = _create_session(authed_client, authed_client.headers)
    r = authed_client.patch(
        f"/api/v1/sessions/{created['id']}",
        json={"breakthrough_note": "finally landed it"},
    )
    assert r.status_code == 200
    assert r.json()["breakthrough_note"] == "finally landed it"


def test_delete_session_soft_deletes(authed_client: TestClient) -> None:
    created = _create_session(authed_client, authed_client.headers)
    dr = authed_client.delete(f"/api/v1/sessions/{created['id']}")
    assert dr.status_code == 204

    engine = get_engine()
    with Session(engine) as db:
        row = db.get(SkateSessionModel, created["id"])
        assert row is not None
        assert row.deleted_at is not None


def test_list_sessions_returns_own_only(client: TestClient, authed_client: TestClient) -> None:
    _create_session(authed_client, authed_client.headers, spot_label="Mine")
    client.post(
        "/api/v1/sessions",
        json={"spot_label": "Theirs"},
        headers={"Authorization": "Bearer dev:other-user-999"},
    )

    r = authed_client.get("/api/v1/me/sessions")
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["spot_label"] != "Theirs" for i in items)
    assert any(i["spot_label"] == "Mine" for i in items)


def test_list_sessions_excludes_soft_deleted(authed_client: TestClient) -> None:
    kept = _create_session(authed_client, authed_client.headers, spot_label="Kept")
    gone = _create_session(authed_client, authed_client.headers, spot_label="Gone")
    authed_client.delete(f"/api/v1/sessions/{gone['id']}")

    r = authed_client.get("/api/v1/me/sessions")
    ids = {i["id"] for i in r.json()["items"]}
    assert kept["id"] in ids
    assert gone["id"] not in ids


def test_list_sessions_paginates_with_cursor(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as db:
        for i in range(5):
            row = SkateSessionModel(
                id=f"00000000-0000-4000-8000-00000000000{i}",
                user_id="test-user-001",
                spot_label=f"S{i}",
                started_at=datetime(2026, 5, 30, 10, i, 0, tzinfo=timezone.utc),
            )
            db.add(row)
        db.commit()

    r1 = authed_client.get("/api/v1/me/sessions", params={"limit": 2})
    assert r1.status_code == 200
    page1 = r1.json()
    assert len(page1["items"]) == 2
    assert page1["next_cursor"]

    r2 = authed_client.get(
        "/api/v1/me/sessions",
        params={"limit": 2, "cursor": page1["next_cursor"]},
    )
    assert r2.status_code == 200
    page2 = r2.json()
    assert len(page2["items"]) >= 1
    assert page1["items"][0]["id"] != page2["items"][0]["id"]


def test_participants_endpoint_returns_501(authed_client: TestClient) -> None:
    created = _create_session(authed_client, authed_client.headers)
    r = authed_client.post(
        f"/api/v1/sessions/{created['id']}/participants",
        json={"user_id": "someone"},
    )
    assert r.status_code == 501
    assert "not implemented" in r.json()["detail"].lower()
