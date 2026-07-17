"""Complete-upload for V1 session clips (Step 5B.3 backend)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import get_engine
from app.models import ClipJobModel, ClipModel


_UPLOAD_BODY = {
    "duration_seconds": 4.5,
    "width_px": 1080,
    "height_px": 1920,
    "content_type": "video/mp4",
    "size_bytes": 1024,
}


def _initiate(authed_client: TestClient, session_id: str | None = None) -> dict:
    payload = {**_UPLOAD_BODY, **({"session_id": session_id} if session_id else {})}
    r = authed_client.post("/api/v1/clips/initiate-upload", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _write_local_upload(client: TestClient, storage_key: str, data: bytes = b"fake-mp4-bytes") -> None:
    upload_root = Path(client.app.state.upload_dir)
    dest = upload_root / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def test_complete_upload_enqueues_analysis(authed_client: TestClient) -> None:
    session_id = authed_client.post("/api/v1/sessions", json={"spot_label": "Test"}).json()["id"]
    initiated = _initiate(authed_client, session_id)
    clip_id = initiated["clip_id"]
    _write_local_upload(authed_client, initiated["storage_key"])

    r = authed_client.post(f"/api/v1/clips/{clip_id}/complete-upload")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["upload_status"] == "analyzing"
    assert body["session_id"] == session_id

    engine = get_engine()
    with Session(engine) as db:
        job = db.get(ClipJobModel, clip_id)
        assert job is not None
        assert job.user_id == "test-user-001"
        assert job.input_reference == f"storage:{initiated['storage_key']}"


def test_complete_upload_404_when_storage_missing(authed_client: TestClient) -> None:
    initiated = _initiate(authed_client)
    clip_id = initiated["clip_id"]
    r = authed_client.post(f"/api/v1/clips/{clip_id}/complete-upload")
    assert r.status_code == 404


def test_complete_upload_404_for_other_users_clip(
    client: TestClient, authed_client: TestClient
) -> None:
    initiated = _initiate(authed_client)
    _write_local_upload(authed_client, initiated["storage_key"])
    r = client.post(
        f"/api/v1/clips/{initiated['clip_id']}/complete-upload",
        headers={"Authorization": "Bearer dev:other-user-999"},
    )
    assert r.status_code == 404


def test_complete_upload_409_when_already_analyzed(authed_client: TestClient) -> None:
    initiated = _initiate(authed_client)
    clip_id = initiated["clip_id"]

    engine = get_engine()
    with Session(engine) as db:
        clip = db.get(ClipModel, clip_id)
        assert clip is not None
        clip.upload_status = "analyzed"
        db.add(clip)
        db.commit()

    again = authed_client.post(f"/api/v1/clips/{clip_id}/complete-upload")
    assert again.status_code == 409


def test_complete_upload_422_when_object_empty(authed_client: TestClient) -> None:
    """An empty/unreadable object is rejected, deleted, and never charges quota."""
    initiated = _initiate(authed_client)
    clip_id = initiated["clip_id"]
    _write_local_upload(authed_client, initiated["storage_key"], b"")

    r = authed_client.post(f"/api/v1/clips/{clip_id}/complete-upload")
    assert r.status_code == 422, r.text

    upload_root = Path(authed_client.app.state.upload_dir)
    assert not (upload_root / initiated["storage_key"]).exists()

    engine = get_engine()
    with Session(engine) as db:
        clip = db.get(ClipModel, clip_id)
        assert clip is not None
        assert clip.upload_status == "pending"
        assert db.get(ClipJobModel, clip_id) is None


def test_complete_upload_413_when_over_max_size(
    authed_client: TestClient, monkeypatch
) -> None:
    """Actual bytes above the server ceiling are rejected regardless of declared size."""
    monkeypatch.setenv("ONFLOW_CLIP_MAX_UPLOAD_BYTES", "16")
    from app.core.config import get_settings

    get_settings.cache_clear()

    initiated = _initiate(authed_client)
    clip_id = initiated["clip_id"]
    _write_local_upload(authed_client, initiated["storage_key"], b"x" * 64)

    r = authed_client.post(f"/api/v1/clips/{clip_id}/complete-upload")
    assert r.status_code == 413, r.text

    upload_root = Path(authed_client.app.state.upload_dir)
    assert not (upload_root / initiated["storage_key"]).exists()

    engine = get_engine()
    with Session(engine) as db:
        assert db.get(ClipJobModel, clip_id) is None


def test_complete_upload_records_server_measured_size(authed_client: TestClient) -> None:
    """Server-measured byte size replaces the untrusted client-declared value."""
    initiated = _initiate(authed_client)  # declares size_bytes=1024
    clip_id = initiated["clip_id"]
    payload = b"fake-mp4-bytes"  # 14 bytes, differs from declared 1024
    _write_local_upload(authed_client, initiated["storage_key"], payload)

    r = authed_client.post(f"/api/v1/clips/{clip_id}/complete-upload")
    assert r.status_code == 200, r.text

    engine = get_engine()
    with Session(engine) as db:
        clip = db.get(ClipModel, clip_id)
        assert clip is not None
        assert clip.size_bytes == len(payload)


def test_complete_upload_runs_existing_pipeline(
    authed_client: TestClient, sample_valid_mp4_bytes: bytes
) -> None:
    initiated = _initiate(authed_client)
    clip_id = initiated["clip_id"]
    _write_local_upload(authed_client, initiated["storage_key"], sample_valid_mp4_bytes)

    r = authed_client.post(f"/api/v1/clips/{clip_id}/complete-upload")
    assert r.status_code == 200

    deadline = time.time() + 20.0
    terminal = None
    while time.time() < deadline:
        engine = get_engine()
        with Session(engine) as db:
            clip = db.get(ClipModel, clip_id)
            if clip and clip.upload_status in ("analyzed", "failed"):
                terminal = clip.upload_status
                break
        time.sleep(0.05)

    assert terminal == "analyzed", f"clip did not analyze, last status={terminal}"
