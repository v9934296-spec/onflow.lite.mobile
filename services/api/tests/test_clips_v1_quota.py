"""V1 upload quota accounting (Tier 2 hardening).

Two guarantees:
  1. complete-upload records a real ``quota_source`` (never NULL), so monthly-free
     accounting (which counts NULL/'monthly' rows) stays correct.
  2. The product quota is charged at complete-upload, not initiate — an abandoned
     initiate never consumes a bonus credit.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import get_engine
from app.models import ClipJobModel

_UPLOAD_BODY = {
    "duration_seconds": 4.5,
    "width_px": 1080,
    "height_px": 1920,
    "content_type": "video/mp4",
    "size_bytes": 1024,
}


def _initiate(client: TestClient) -> dict:
    r = client.post("/api/v1/clips/initiate-upload", json=_UPLOAD_BODY)
    assert r.status_code == 201, r.text
    return r.json()


def _write_local_upload(client: TestClient, storage_key: str) -> None:
    dest = Path(client.app.state.upload_dir) / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"fake-mp4-bytes")


def _job_quota_source(clip_id: str) -> str | None:
    with Session(get_engine()) as db:
        job = db.get(ClipJobModel, clip_id)
        assert job is not None
        return job.quota_source


def test_complete_upload_records_quota_source(authed_client: TestClient) -> None:
    initiated = _initiate(authed_client)
    clip_id = initiated["clip_id"]
    _write_local_upload(authed_client, initiated["storage_key"])

    assert authed_client.post(f"/api/v1/clips/{clip_id}/complete-upload").status_code == 200
    # Under the test's generous free cap this is a monthly slot — crucially NOT None.
    assert _job_quota_source(clip_id) == "monthly"


def test_initiate_does_not_consume_bonus_until_complete(
    authed_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_RATE_LIMIT_FREE", "1")
    db = authed_client.app.state.db
    db.ensure_invite_claim_user("test-user-001", "free")
    db.add_bonus_analyses("test-user-001", 2)
    assert db.get_bonus_analyses("test-user-001") == 2

    # First clip uses the single monthly slot; bonus untouched.
    c1 = _initiate(authed_client)
    _write_local_upload(authed_client, c1["storage_key"])
    assert authed_client.post(f"/api/v1/clips/{c1['clip_id']}/complete-upload").status_code == 200
    assert _job_quota_source(c1["clip_id"]) == "monthly"
    assert db.get_bonus_analyses("test-user-001") == 2

    # Second clip is over the monthly cap. Initiate must NOT consume bonus...
    c2 = _initiate(authed_client)
    assert db.get_bonus_analyses("test-user-001") == 2
    # ...only complete-upload charges it, and records quota_source='bonus'.
    _write_local_upload(authed_client, c2["storage_key"])
    assert authed_client.post(f"/api/v1/clips/{c2['clip_id']}/complete-upload").status_code == 200
    assert db.get_bonus_analyses("test-user-001") == 1
    assert _job_quota_source(c2["clip_id"]) == "bonus"
