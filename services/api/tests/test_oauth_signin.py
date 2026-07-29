"""OAuth sign-in routes (Google / Apple) — verifier is mocked."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import UserModel
from app.services.apple_auth import AppleAuthError
from app.services.google_auth import GoogleAuthError


@pytest.fixture
def oauth_client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ONFLOW_DATABASE_URL", f"sqlite:///{(tmp_path / 'oauth.db').as_posix()}")
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ONFLOW_GOOGLE_CLIENT_IDS", "web-id,ios-id")
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_oauth_invalid_token_returns_401(
    oauth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    c = oauth_client

    def _raise_google(_t: str) -> dict:
        raise GoogleAuthError("bad")

    def _raise_apple(_t: str) -> dict:
        raise AppleAuthError("bad")

    if provider == "google":
        monkeypatch.setattr("app.routers.oauth_signin.verify_google_id_token", _raise_google)
    else:
        monkeypatch.setattr("app.routers.oauth_signin.verify_apple_id_token", _raise_apple)

    path = f"/api/v1/auth/{provider}"
    r = c.post(path, json={"id_token": "x" * 20})
    assert r.status_code == 401


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_oauth_unverified_email_returns_403(
    oauth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    c = oauth_client

    def _claims(_t: str) -> dict:
        if provider == "google":
            return {
                "sub": "sub-u1",
                "email": "u1@onflow.test",
                "email_verified": False,
            }
        return {
            "sub": "sub-u1",
            "email": "u1@onflow.test",
            "email_verified": False,
        }

    if provider == "google":
        monkeypatch.setattr(
            "app.routers.oauth_signin.verify_google_id_token",
            _claims,
        )
    else:
        monkeypatch.setattr(
            "app.routers.oauth_signin.verify_apple_id_token",
            _claims,
        )

    path = f"/api/v1/auth/{provider}"
    r = c.post(path, json={"id_token": "x" * 40})
    assert r.status_code == 403


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_oauth_new_user_gets_bonus_credit(
    oauth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    c = oauth_client

    def _claims(_t: str) -> dict:
        if provider == "google":
            return {
                "sub": "new-sub-1",
                "email": "new1@onflow.test",
                "email_verified": True,
            }
        return {
            "sub": "new-sub-1",
            "email": "new1@onflow.test",
            "email_verified": True,
        }

    if provider == "google":
        monkeypatch.setattr("app.routers.oauth_signin.verify_google_id_token", _claims)
    else:
        monkeypatch.setattr("app.routers.oauth_signin.verify_apple_id_token", _claims)

    path = f"/api/v1/auth/{provider}"
    r = c.post(path, json={"id_token": "y" * 40})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_new_user"] is True
    assert data["bonus_analyses_remaining"] == 1


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_oauth_returning_user_no_extra_bonus(
    oauth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    c = oauth_client

    def _claims(_t: str) -> dict:
        if provider == "google":
            return {
                "sub": "ret-sub-1",
                "email": "ret1@onflow.test",
                "email_verified": True,
            }
        return {
            "sub": "ret-sub-1",
            "email": "ret1@onflow.test",
            "email_verified": True,
        }

    if provider == "google":
        monkeypatch.setattr("app.routers.oauth_signin.verify_google_id_token", _claims)
    else:
        monkeypatch.setattr("app.routers.oauth_signin.verify_apple_id_token", _claims)

    path = f"/api/v1/auth/{provider}"
    r1 = c.post(path, json={"id_token": "z" * 40})
    assert r1.status_code == 200
    assert r1.json()["is_new_user"] is True
    r2 = c.post(path, json={"id_token": "z" * 40})
    assert r2.status_code == 200
    data = r2.json()
    assert data["is_new_user"] is False
    assert data["bonus_analyses_remaining"] == 1


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_oauth_links_invite_user_by_email_no_bonus(
    oauth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    c = oauth_client
    from app.core.database import get_engine

    with Session(get_engine()) as session:
        session.add(
            UserModel(
                id="inviteuid01",
                email="invite-merge@onflow.test",
                tier="free",
                auth_provider="invite",
                bonus_analyses_granted=0,
                bonus_analyses_used=0,
            )
        )
        session.commit()

    def _claims(_t: str) -> dict:
        if provider == "google":
            return {
                "sub": "link-sub-1",
                "email": "invite-merge@onflow.test",
                "email_verified": True,
            }
        return {
            "sub": "link-sub-1",
            "email": "invite-merge@onflow.test",
            "email_verified": True,
        }

    if provider == "google":
        monkeypatch.setattr("app.routers.oauth_signin.verify_google_id_token", _claims)
    else:
        monkeypatch.setattr("app.routers.oauth_signin.verify_apple_id_token", _claims)

    path = f"/api/v1/auth/{provider}"
    r = c.post(path, json={"id_token": "w" * 40})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user_id"] == "inviteuid01"
    assert data["is_new_user"] is False
    assert data["bonus_analyses_remaining"] == 0

    with Session(get_engine()) as session:
        row = session.get(UserModel, "inviteuid01")
        assert row is not None
        assert row.auth_provider == "invite"
        if provider == "google":
            assert row.google_sub == "link-sub-1"
        else:
            assert row.apple_sub == "link-sub-1"
