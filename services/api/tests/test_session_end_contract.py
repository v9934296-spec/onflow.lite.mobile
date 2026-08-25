"""BE-003 — first ended_at wins. BE-004 — ended-session clip window."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.database import get_engine
from app.models import FeedEventModel
from tests.conftest import write_presigned_upload


def _headers(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/session", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def _create_session(client: TestClient, headers: dict[str, str]) -> str:
    r = client.post("/api/v1/sessions", json={"spot_label": "Park"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_second_ended_at_does_not_overwrite(client: TestClient) -> None:
    headers = _headers(client, "end-conflict@onflow.test")
    session_id = _create_session(client, headers)

    first = "2026-08-01T10:00:00Z"
    second = "2026-08-03T18:00:00Z"
    r1 = client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"ended_at": first},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["ended_at"] == first

    r2 = client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"ended_at": second, "notes": "stale phone"},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["ended_at"] == first
    assert body["notes"] == "stale phone"


def test_identical_ended_at_replay_is_accepted(client: TestClient) -> None:
    headers = _headers(client, "end-replay@onflow.test")
    session_id = _create_session(client, headers)
    ended = "2026-08-01T10:00:00Z"
    assert (
        client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"ended_at": ended},
            headers=headers,
        ).status_code
        == 200
    )
    replay = client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"ended_at": ended},
        headers=headers,
    )
    assert replay.status_code == 200
    assert replay.json()["ended_at"] == ended


def _init_body(session_id: str, captured_at: str | None = None) -> dict:
    body: dict = {
        "session_id": session_id,
        "duration_seconds": 4.0,
        "width_px": 1080,
        "height_px": 1920,
        "content_type": "video/mp4",
        "size_bytes": 12,
    }
    if captured_at is not None:
        body["captured_at"] = captured_at
    return body


def test_open_session_still_accepts_upload(client: TestClient) -> None:
    headers = _headers(client, "open-up@onflow.test")
    session_id = _create_session(client, headers)
    r = client.post(
        "/api/v1/clips/initiate-upload",
        json=_init_body(session_id),
        headers=headers,
    )
    assert r.status_code == 201, r.text


def test_capture_after_ended_at_is_rejected(client: TestClient) -> None:
    headers = _headers(client, "late-cap@onflow.test")
    session_id = _create_session(client, headers)
    now = datetime.now(timezone.utc)
    ended = now.isoformat().replace("+00:00", "Z")
    captured = (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    assert (
        client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"ended_at": ended},
            headers=headers,
        ).status_code
        == 200
    )

    r = client.post(
        "/api/v1/clips/initiate-upload",
        json=_init_body(session_id, captured_at=captured),
        headers=headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "capture_after_session_end"


def test_capture_before_ended_at_is_accepted_inside_window(client: TestClient) -> None:
    headers = _headers(client, "early-cap@onflow.test")
    session_id = _create_session(client, headers)
    now = datetime.now(timezone.utc)
    ended = now.isoformat().replace("+00:00", "Z")
    captured = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    assert (
        client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"ended_at": ended},
            headers=headers,
        ).status_code
        == 200
    )

    r = client.post(
        "/api/v1/clips/initiate-upload",
        json=_init_body(session_id, captured_at=captured),
        headers=headers,
    )
    assert r.status_code == 201, r.text


def test_ended_session_upload_window_expires(client: TestClient) -> None:
    headers = _headers(client, "window@onflow.test")
    session_id = _create_session(client, headers)
    ended = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat().replace(
        "+00:00", "Z"
    )
    captured = (datetime.now(timezone.utc) - timedelta(hours=26)).isoformat().replace(
        "+00:00", "Z"
    )
    assert (
        client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"ended_at": ended},
            headers=headers,
        ).status_code
        == 200
    )

    r = client.post(
        "/api/v1/clips/initiate-upload",
        json=_init_body(session_id, captured_at=captured),
        headers=headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "session_end_upload_window_expired"


def test_legacy_client_without_captured_at_still_uploads_inside_window(
    client: TestClient,
) -> None:
    """onflow-lite does not send captured_at. Keep that path working for 24h."""
    headers = _headers(client, "legacy-up@onflow.test")
    session_id = _create_session(client, headers)
    ended = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    assert (
        client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"ended_at": ended},
            headers=headers,
        ).status_code
        == 200
    )
    r = client.post(
        "/api/v1/clips/initiate-upload",
        json=_init_body(session_id),
        headers=headers,
    )
    assert r.status_code == 201, r.text


def test_complete_upload_rejects_when_window_already_expired(
    client: TestClient,
) -> None:
    """Initiate while open, then the session ages past the window before complete."""
    from app.services.video_signature import MINIMAL_VIDEO_SNIFF_BYTES

    headers = _headers(client, "complete-window@onflow.test")
    session_id = _create_session(client, headers)
    init = client.post(
        "/api/v1/clips/initiate-upload",
        json=_init_body(session_id),
        headers=headers,
    )
    assert init.status_code == 201, init.text
    clip_id = init.json()["clip_id"]
    write_presigned_upload(client, init.json()["storage_key"], MINIMAL_VIDEO_SNIFF_BYTES)

    stale = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat().replace(
        "+00:00", "Z"
    )
    # Directly age the session past the window so complete-upload is the gate.
    from sqlmodel import Session as DbSession

    from app.core.database import get_engine
    from app.models import SkateSessionModel

    with DbSession(get_engine()) as db:
        row = db.get(SkateSessionModel, session_id)
        assert row is not None
        row.ended_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db.add(row)
        db.commit()

    complete = client.post(f"/api/v1/clips/{clip_id}/complete-upload", headers=headers)
    assert complete.status_code == 409, complete.text
    assert complete.json()["detail"] == "session_end_upload_window_expired"
    _ = stale


def test_concurrent_first_end_keeps_one_winner_and_one_recap(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two overlapping PATCHes both snapshot NULL; only one ended_at is durable."""
    from app.routers import sessions as sessions_mod

    headers = _headers(client, "end-race@onflow.test")
    session_id = _create_session(client, headers)
    first = "2026-08-01T10:00:00Z"
    second = "2026-08-03T18:00:00Z"
    barrier = threading.Barrier(2, timeout=15)
    orig = sessions_mod._active_session

    def gated(db, sid, *, for_user=None):  # type: ignore[no-untyped-def]
        row = orig(db, sid, for_user=for_user)
        if row is not None and row.ended_at is None:
            barrier.wait()
        return row

    monkeypatch.setattr(sessions_mod, "_active_session", gated)

    def _patch(ended: str, notes: str):
        return client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"ended_at": ended, "notes": notes},
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_a = pool.submit(_patch, first, "device-a")
        f_b = pool.submit(_patch, second, "device-b")
        r_a = f_a.result(timeout=20)
        r_b = f_b.result(timeout=20)

    assert r_a.status_code == 200, r_a.text
    assert r_b.status_code == 200, r_b.text
    stored = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
    assert stored.status_code == 200, stored.text
    winner = stored.json()["ended_at"]
    assert winner in {first, second}
    assert r_a.json()["ended_at"] == winner
    assert r_b.json()["ended_at"] == winner

    with Session(get_engine()) as db:
        recaps = list(
            db.exec(
                select(FeedEventModel).where(
                    FeedEventModel.skate_session_id == session_id,
                    FeedEventModel.event_type == "session_recap",
                    FeedEventModel.deleted_at.is_(None),  # type: ignore[union-attr]
                )
            )
        )
    assert len(recaps) == 1


def test_complete_upload_keeps_captured_at_across_ended_session(
    client: TestClient,
) -> None:
    """Capture before end; initiate after end inside 24h; complete must succeed."""
    from app.services.video_signature import MINIMAL_VIDEO_SNIFF_BYTES

    headers = _headers(client, "clock-complete@onflow.test")
    session_id = _create_session(client, headers)
    now = datetime.now(timezone.utc)
    ended = now.isoformat().replace("+00:00", "Z")
    captured = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    assert (
        client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"ended_at": ended},
            headers=headers,
        ).status_code
        == 200
    )

    body = _init_body(session_id, captured_at=captured)
    body["size_bytes"] = max(len(MINIMAL_VIDEO_SNIFF_BYTES), 1)
    init = client.post("/api/v1/clips/initiate-upload", json=body, headers=headers)
    assert init.status_code == 201, init.text
    write_presigned_upload(client, init.json()["storage_key"], MINIMAL_VIDEO_SNIFF_BYTES)
    complete = client.post(
        f"/api/v1/clips/{init.json()['clip_id']}/complete-upload",
        headers=headers,
    )
    assert complete.status_code == 200, complete.text


def test_legacy_complete_upload_without_captured_at_uses_window_only(
    client: TestClient,
) -> None:
    """onflow-lite omits captured_at; complete must not treat initiate time as capture."""
    from app.services.video_signature import MINIMAL_VIDEO_SNIFF_BYTES

    headers = _headers(client, "legacy-complete@onflow.test")
    session_id = _create_session(client, headers)
    ended = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    assert (
        client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"ended_at": ended},
            headers=headers,
        ).status_code
        == 200
    )
    body = _init_body(session_id)
    body["size_bytes"] = max(len(MINIMAL_VIDEO_SNIFF_BYTES), 1)
    init = client.post("/api/v1/clips/initiate-upload", json=body, headers=headers)
    assert init.status_code == 201, init.text
    write_presigned_upload(client, init.json()["storage_key"], MINIMAL_VIDEO_SNIFF_BYTES)
    complete = client.post(
        f"/api/v1/clips/{init.json()['clip_id']}/complete-upload",
        headers=headers,
    )
    assert complete.status_code == 200, complete.text
