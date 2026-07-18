from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.database import get_engine
from app.models import SessionAttemptModel, SkateSessionModel


def _headers(client: TestClient, email: str = "attempts@onflow.test") -> dict[str, str]:
    r = client.post("/api/v1/auth/session", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def _create_session(client: TestClient, headers: dict[str, str]) -> str:
    r = client.post("/api/v1/sessions", json={"spot_label": "Park"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_sync_and_list_session_attempts(client: TestClient) -> None:
    headers = _headers(client)
    session_id = _create_session(client, headers)

    payload = {
        "attempts": [
            {
                "id": "client-att-1",
                "session_id": session_id,
                "trick_id": "kickflip",
                "canonical_name": "Kickflip",
                "outcome": "landed",
                "logged_at": "2026-07-17T12:00:00Z",
            },
            {
                "id": "client-att-2",
                "session_id": session_id,
                "trick_id": "heelflip",
                "canonical_name": "Heelflip",
                "outcome": "missed",
                "logged_at": "2026-07-17T12:01:00Z",
            },
        ]
    }
    r = client.post("/api/v1/session-attempts/sync", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["accepted"]) == {"client-att-1", "client-att-2"}
    assert body["rejected"] == []

    # Idempotent replay
    r2 = client.post("/api/v1/session-attempts/sync", json=payload, headers=headers)
    assert r2.status_code == 200
    assert set(r2.json()["accepted"]) == {"client-att-1", "client-att-2"}

    listed = client.get(f"/api/v1/sessions/{session_id}/attempts", headers=headers)
    assert listed.status_code == 200, listed.text
    attempts = listed.json()["attempts"]
    assert len(attempts) == 2
    assert attempts[0]["id"] == "client-att-1"
    assert attempts[0]["outcome"] == "landed"


def test_sync_rejects_foreign_session(client: TestClient) -> None:
    ha = _headers(client, "owner-a@onflow.test")
    hb = _headers(client, "owner-b@onflow.test")
    session_a = _create_session(client, ha)

    r = client.post(
        "/api/v1/session-attempts/sync",
        headers=hb,
        json={
            "attempts": [
                {
                    "id": "x1",
                    "session_id": session_a,
                    "trick_id": "ollie",
                    "canonical_name": "Ollie",
                    "outcome": "landed",
                    "logged_at": "2026-07-17T12:00:00Z",
                }
            ]
        },
    )
    assert r.status_code == 200
    assert r.json()["accepted"] == []
    assert r.json()["rejected"][0]["reason"] == "session_not_found"


def test_session_attempt_count_uses_synced_rows(client: TestClient) -> None:
    headers = _headers(client, "count-att@onflow.test")
    session_id = _create_session(client, headers)
    client.post(
        "/api/v1/session-attempts/sync",
        headers=headers,
        json={
            "attempts": [
                {
                    "id": f"c-{i}",
                    "session_id": session_id,
                    "trick_id": "kickflip",
                    "canonical_name": "Kickflip",
                    "outcome": "landed" if i % 2 == 0 else "missed",
                    "logged_at": f"2026-07-17T12:0{i}:00Z",
                }
                for i in range(3)
            ]
        },
    )
    r = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["attempt_count"] == 3


def test_account_delete_purges_session_attempts(client: TestClient) -> None:
    headers = _headers(client, "del-att@onflow.test")
    session_id = _create_session(client, headers)
    client.post(
        "/api/v1/session-attempts/sync",
        headers=headers,
        json={
            "attempts": [
                {
                    "id": "del-1",
                    "session_id": session_id,
                    "trick_id": "kickflip",
                    "canonical_name": "Kickflip",
                    "outcome": "landed",
                    "logged_at": "2026-07-17T12:00:00Z",
                }
            ]
        },
    )
    user_id = client.get("/api/v1/account/me", headers=headers).json()["user_id"]
    with Session(get_engine()) as db:
        assert db.exec(
            select(SessionAttemptModel).where(SessionAttemptModel.user_id == user_id)
        ).first() is not None

    assert client.delete("/api/v1/account", headers=headers).status_code == 202

    with Session(get_engine()) as db:
        assert (
            db.exec(select(SessionAttemptModel).where(SessionAttemptModel.user_id == user_id)).first()
            is None
        )
