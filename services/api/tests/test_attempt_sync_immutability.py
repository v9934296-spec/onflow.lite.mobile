"""BE-001 — attempt sync is an immutable replay contract, not an upsert.

The manual outcome is the authoritative record of what the skater did. These
tests pin the one data bug that would be unrecoverable: a stale queued row from
an offline phone silently rewriting history.
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import get_engine
from app.models import SessionAttemptModel

LOGGED_AT = "2026-07-17T12:00:00Z"


def _headers(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/session", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def _create_session(client: TestClient, headers: dict[str, str]) -> str:
    r = client.post("/api/v1/sessions", json={"spot_label": "Park"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _attempt(
    session_id: str,
    *,
    attempt_id: str = "att-1",
    trick_id: str = "kickflip",
    canonical_name: str = "Kickflip",
    outcome: str = "landed",
    logged_at: str = LOGGED_AT,
) -> dict[str, str]:
    return {
        "id": attempt_id,
        "session_id": session_id,
        "trick_id": trick_id,
        "canonical_name": canonical_name,
        "outcome": outcome,
        "logged_at": logged_at,
    }


def _sync(client: TestClient, headers: dict[str, str], *attempts: dict[str, str]):
    return client.post(
        "/api/v1/session-attempts/sync",
        json={"attempts": list(attempts)},
        headers=headers,
    )


def _stored(attempt_id: str) -> SessionAttemptModel:
    with Session(get_engine()) as db:
        row = db.get(SessionAttemptModel, attempt_id)
        assert row is not None
        db.expunge(row)
        return row


def _reject_reason(body: dict, attempt_id: str) -> str:
    matches = [r["reason"] for r in body["rejected"] if r["id"] == attempt_id]
    assert matches, f"{attempt_id} was not rejected: {body}"
    return matches[0]


def test_identical_replay_is_accepted_and_mutates_nothing(client: TestClient) -> None:
    headers = _headers(client, "replay@onflow.test")
    session_id = _create_session(client, headers)

    first = _sync(client, headers, _attempt(session_id))
    assert first.status_code == 200, first.text
    assert first.json()["accepted"] == ["att-1"]
    before = _stored("att-1")

    replay = _sync(client, headers, _attempt(session_id))
    assert replay.status_code == 200, replay.text
    assert replay.json()["accepted"] == ["att-1"]
    assert replay.json()["rejected"] == []

    after = _stored("att-1")
    assert after.outcome == before.outcome
    assert after.session_id == before.session_id
    assert after.trick_id == before.trick_id
    assert after.canonical_name == before.canonical_name
    assert after.logged_at == before.logged_at
    assert after.created_at == before.created_at


def test_changed_outcome_is_rejected_and_record_survives(client: TestClient) -> None:
    """The worst available data bug: flipping a recorded outcome."""
    headers = _headers(client, "flip@onflow.test")
    session_id = _create_session(client, headers)

    assert _sync(client, headers, _attempt(session_id, outcome="landed")).status_code == 200

    conflict = _sync(client, headers, _attempt(session_id, outcome="missed"))
    assert conflict.status_code == 200, conflict.text
    body = conflict.json()
    assert body["accepted"] == []
    assert _reject_reason(body, "att-1") == "outcome_immutable"

    assert _stored("att-1").outcome == "landed"


def test_attempt_can_never_move_session(client: TestClient) -> None:
    headers = _headers(client, "move@onflow.test")
    session_a = _create_session(client, headers)
    session_b = _create_session(client, headers)

    assert _sync(client, headers, _attempt(session_a)).status_code == 200

    moved = _sync(client, headers, _attempt(session_b))
    body = moved.json()
    assert body["accepted"] == []
    assert _reject_reason(body, "att-1") == "session_immutable"

    assert _stored("att-1").session_id == session_a


def test_changed_trick_is_rejected(client: TestClient) -> None:
    headers = _headers(client, "trick@onflow.test")
    session_id = _create_session(client, headers)

    assert _sync(client, headers, _attempt(session_id)).status_code == 200

    changed = _sync(
        client,
        headers,
        _attempt(session_id, trick_id="heelflip", canonical_name="Heelflip"),
    )
    body = changed.json()
    assert _reject_reason(body, "att-1") == "attempt_immutable"
    assert _stored("att-1").canonical_name == "Kickflip"


def test_changed_logged_at_is_rejected(client: TestClient) -> None:
    """logged_at is when the skater skated. An offline batch must not rewrite it."""
    headers = _headers(client, "clock@onflow.test")
    session_id = _create_session(client, headers)

    assert _sync(client, headers, _attempt(session_id)).status_code == 200

    changed = _sync(
        client, headers, _attempt(session_id, logged_at="2026-07-20T09:30:00Z")
    )
    assert _reject_reason(changed.json(), "att-1") == "attempt_immutable"
    assert _as_utc(_stored("att-1").logged_at) == datetime(
        2026, 7, 17, 12, 0, tzinfo=timezone.utc
    )


def test_deleted_attempt_cannot_resurrect(client: TestClient) -> None:
    headers = _headers(client, "resurrect@onflow.test")
    session_id = _create_session(client, headers)
    assert _sync(client, headers, _attempt(session_id)).status_code == 200

    with Session(get_engine()) as db:
        row = db.get(SessionAttemptModel, "att-1")
        assert row is not None
        row.deleted_at = datetime(2026, 7, 18, tzinfo=timezone.utc)
        db.add(row)
        db.commit()

    replay = _sync(client, headers, _attempt(session_id))
    body = replay.json()
    assert body["accepted"] == []
    assert _reject_reason(body, "att-1") == "attempt_deleted"

    assert _stored("att-1").deleted_at is not None

    listed = client.get(f"/api/v1/sessions/{session_id}/attempts", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["attempts"] == []


def test_unknown_outcome_is_rejected_at_ingress(client: TestClient) -> None:
    headers = _headers(client, "unknown@onflow.test")
    session_id = _create_session(client, headers)

    r = _sync(client, headers, _attempt(session_id, outcome="unsure"))
    assert r.status_code == 422, r.text


def test_unknown_stored_outcome_is_never_coerced_to_missed(client: TestClient) -> None:
    """A future third value must not be silently downgraded (spec 8.5)."""
    headers = _headers(client, "coerce@onflow.test")
    session_id = _create_session(client, headers)
    assert _sync(client, headers, _attempt(session_id)).status_code == 200

    with Session(get_engine()) as db:
        db.exec(
            sa.text("UPDATE session_attempts SET outcome = 'unsure' WHERE id = 'att-1'")
        )
        db.commit()

    listed = client.get(f"/api/v1/sessions/{session_id}/attempts", headers=headers)
    assert listed.status_code == 200, listed.text
    outcomes = [a["outcome"] for a in listed.json()["attempts"]]
    assert "missed" not in outcomes
    assert outcomes == []


def test_another_account_cannot_claim_an_attempt_id(client: TestClient) -> None:
    owner = _headers(client, "owner@onflow.test")
    intruder = _headers(client, "intruder@onflow.test")
    owner_session = _create_session(client, owner)
    intruder_session = _create_session(client, intruder)

    assert _sync(client, owner, _attempt(owner_session, outcome="landed")).status_code == 200

    hijack = _sync(client, intruder, _attempt(intruder_session, outcome="missed"))
    body = hijack.json()
    assert body["accepted"] == []
    assert _reject_reason(body, "att-1") == "forbidden"

    stored = _stored("att-1")
    assert stored.session_id == owner_session
    assert stored.outcome == "landed"


def test_conflicting_duplicate_within_one_batch_is_rejected(client: TestClient) -> None:
    headers = _headers(client, "dupe@onflow.test")
    session_id = _create_session(client, headers)

    r = _sync(
        client,
        headers,
        _attempt(session_id, outcome="landed"),
        _attempt(session_id, outcome="missed"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert _reject_reason(body, "att-1") == "duplicate_in_batch"
    assert body["accepted"] == []

    with Session(get_engine()) as db:
        assert db.get(SessionAttemptModel, "att-1") is None


def test_identical_duplicate_within_one_batch_is_collapsed(client: TestClient) -> None:
    headers = _headers(client, "dupe-ok@onflow.test")
    session_id = _create_session(client, headers)

    r = _sync(client, headers, _attempt(session_id), _attempt(session_id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] == ["att-1"]
    assert body["rejected"] == []


def test_account_scoped_uniqueness_constraint_exists(client: TestClient) -> None:
    """The invariant the sync contract depends on is enforced by the schema."""
    _headers(client, "constraint@onflow.test")
    inspector = sa.inspect(get_engine())
    indexes = {ix["name"]: ix for ix in inspector.get_indexes("session_attempts")}
    unique = indexes.get("uq_session_attempts_user_attempt")
    assert unique is not None, f"missing constraint. present: {sorted(indexes)}"
    assert unique["unique"]
    assert set(unique["column_names"]) == {"user_id", "id"}


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
