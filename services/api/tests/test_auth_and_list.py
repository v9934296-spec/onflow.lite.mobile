from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import submit_clip_via_presigned, write_presigned_upload


def test_claim_invalid_code_when_codes_configured(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_DATABASE_PATH", str(tmp_path / "onflow.db"))
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ONFLOW_BETA_CODES", "grind-01")
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/claim", json={"code": "wrong"})
        assert r.status_code == 422


def test_clip_submission_monthly_quota_exceeded_returns_429(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_DATABASE_PATH", str(tmp_path / "onflow.db"))
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ONFLOW_RATE_LIMIT_FREE", "3")
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/session", json={"email": "rate-limit@onflow.test"})
        assert r.status_code == 200
        c.app.state.db.set_user_tier(r.json()["user_id"], "free")
        h = {"Authorization": f"Bearer {r.json()['session_token']}"}
        for _ in range(3):
            submit_clip_via_presigned(c, h, video_bytes=b"x")
        initiated = c.post(
            "/api/v1/clips/initiate-upload",
            json={
                "duration_seconds": 4.5,
                "width_px": 1080,
                "height_px": 1920,
                "content_type": "video/mp4",
                "size_bytes": 1024,
            },
            headers=h,
        )
        assert initiated.status_code == 201, initiated.text
        write_presigned_upload(c, initiated.json()["storage_key"], b"x")
        r4 = c.post(
            f"/api/v1/clips/{initiated.json()['clip_id']}/complete-upload",
            headers=h,
        )
        assert r4.status_code == 429


def test_post_clips_401_without_bearer_when_jwt_secret_set(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_DATABASE_PATH", str(tmp_path / "onflow.db"))
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/api/v1/clips/initiate-upload",
            json={
                "duration_seconds": 4.5,
                "width_px": 1080,
                "height_px": 1920,
                "content_type": "video/mp4",
                "size_bytes": 1024,
            },
        )
        assert r.status_code == 401


def test_claim_ok_when_codes_configured(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_DATABASE_PATH", str(tmp_path / "onflow.db"))
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ONFLOW_BETA_CODES", "grind-01")
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/claim", json={"code": "grind-01"})
        assert r.status_code == 200
        b = r.json()
        assert b["token"].startswith("dev:")
        assert len(b["user_id"]) == 16


def test_session_with_invite_code_sets_pro_tier(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_DATABASE_PATH", str(tmp_path / "onflow.db"))
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ONFLOW_BETA_CODES", "flow1-12,other")
    monkeypatch.setenv("ONFLOW_BETA_PRO_CODES", "flow1-12")
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/api/v1/auth/session",
            json={"email": "pro-tester@onflow.test", "invite_code": "flow1-12"},
        )
        assert r.status_code == 200
        uid = r.json()["user_id"]
        q = c.get(
            "/api/v1/account/quota",
            headers={"Authorization": f"Bearer {r.json()['session_token']}"},
        )
        assert q.status_code == 200
        assert q.json()["tier"] == "pro"
        assert q.json()["monthly_free_remaining"] is None


def test_session_returns_token(client: TestClient) -> None:
    r = client.post("/api/v1/auth/session", json={"email": "User@Example.COM"})
    assert r.status_code == 200
    b = r.json()
    assert b["email"] == "user@example.com"
    assert len(b["session_token"]) >= 32
    assert len(b["user_id"]) == 36


def test_list_jobs_empty(client: TestClient, auth_headers: dict[str, str]) -> None:
    r = client.get("/api/v1/clips/jobs", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_job_isolated_between_users(
    client: TestClient, auth_headers: dict[str, str], sample_valid_mp4_bytes: bytes
) -> None:
    r = client.post(
        "/api/v1/auth/session",
        json={"email": "other@onflow.test"},
    )
    assert r.status_code == 200
    other = {"Authorization": f"Bearer {r.json()['session_token']}"}

    job_id = submit_clip_via_presigned(
        client, auth_headers, video_bytes=sample_valid_mp4_bytes
    )

    denied = client.get(f"/api/v1/clips/jobs/{job_id}", headers=other)
    assert denied.status_code == 404
