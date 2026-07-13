from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.auth import issue_onflow_access_token


def test_delete_account_requires_auth(client: TestClient) -> None:
    r = client.delete("/api/v1/account")
    assert r.status_code == 401


def test_delete_account_202_and_session_invalidated(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.delete("/api/v1/account", headers=auth_headers)
    assert r.status_code == 202, r.text
    assert r.headers["Cache-Control"] == "no-store"
    assert r.json() == {
        "status": "queued",
        "message": "Account deletion queued. Your clips will be permanently removed within 24 hours.",
    }
    r2 = client.get("/api/v1/account/me", headers=auth_headers)
    assert r2.status_code == 401


def test_delete_account_idempotent_with_dev_bearer(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    uid = client.get("/api/v1/account/me", headers=auth_headers).json()["user_id"]
    dev = {"Authorization": f"Bearer dev:{uid}"}
    r1 = client.delete("/api/v1/account", headers=dev)
    assert r1.status_code == 202
    r2 = client.delete("/api/v1/account", headers=dev)
    assert r2.status_code == 202


def test_delete_account_invalidates_jwt(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("ONFLOW_DATABASE_URL", f"sqlite:///{tmp_path / 'jwt_del.db'}")
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "up"))
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        sr = c.post("/api/v1/auth/session", json={"email": "jwt-del@onflow.test"})
        assert sr.status_code == 200
        uid = sr.json()["user_id"]
        token = issue_onflow_access_token(uid)
        headers = {"Authorization": f"Bearer {token}"}
        dr = c.delete("/api/v1/account", headers=headers)
        assert dr.status_code == 202
        mr = c.get("/api/v1/account/me", headers=headers)
        assert mr.status_code == 401
