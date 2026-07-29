"""Session-aware clip initiate-upload (Step 5B.1)."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import get_engine
from app.models import ClipModel


_UPLOAD_BODY = {
    "duration_seconds": 4.5,
    "width_px": 1080,
    "height_px": 1920,
    "content_type": "video/mp4",
    "size_bytes": 5_242_880,
}


def _create_session(client: TestClient) -> str:
    r = client.post("/api/v1/sessions", json={"spot_label": "Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_initiate_upload_without_session_id(authed_client: TestClient) -> None:
    r = authed_client.post("/api/v1/clips/initiate-upload", json=_UPLOAD_BODY)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["clip_id"]
    assert body["upload_url"]
    assert body["storage_key"]

    engine = get_engine()
    with Session(engine) as db:
        clip = db.get(ClipModel, body["clip_id"])
        assert clip is not None
        assert clip.session_id is None


def test_initiate_upload_with_session_id(authed_client: TestClient) -> None:
    session_id = _create_session(authed_client)
    payload = {**_UPLOAD_BODY, "session_id": session_id}
    r = authed_client.post("/api/v1/clips/initiate-upload", json=payload)
    assert r.status_code == 201, r.text
    clip_id = r.json()["clip_id"]

    engine = get_engine()
    with Session(engine) as db:
        clip = db.get(ClipModel, clip_id)
        assert clip is not None
        assert clip.session_id == session_id


def test_initiate_upload_other_users_session_returns_403(
    client: TestClient, authed_client: TestClient
) -> None:
    session_id = _create_session(authed_client)
    payload = {**_UPLOAD_BODY, "session_id": session_id}
    r = client.post(
        "/api/v1/clips/initiate-upload",
        json=payload,
        headers={"Authorization": "Bearer dev:other-user-999"},
    )
    assert r.status_code == 403


def test_initiate_upload_nonexistent_session_returns_404(authed_client: TestClient) -> None:
    payload = {
        **_UPLOAD_BODY,
        "session_id": "00000000-0000-4000-8000-000000000099",
    }
    r = authed_client.post("/api/v1/clips/initiate-upload", json=payload)
    assert r.status_code == 404
