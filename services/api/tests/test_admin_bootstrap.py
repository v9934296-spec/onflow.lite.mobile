"""Admin bootstrap hardening: verified email, strict env parsing, audit events."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core.admin import parse_admin_emails_strict
from app.models import AdminRoleEventModel, UserModel


def test_parse_admin_emails_strict_accepts_valid_list() -> None:
    assert parse_admin_emails_strict("Ops@OnFlow.test, founder@onflow.test") == {
        "ops@onflow.test",
        "founder@onflow.test",
    }


@pytest.mark.parametrize(
    "raw,fragment",
    [
        ("ops@onflow.test,,founder@onflow.test", "empty entries"),
        ("not-an-email", "invalid email"),
        ("ops@onflow.test,ops@onflow.test", "duplicate"),
    ],
)
def test_parse_admin_emails_strict_rejects_malformed(raw: str, fragment: str) -> None:
    with pytest.raises(ValueError) as exc:
        parse_admin_emails_strict(raw)
    assert fragment in str(exc.value).lower()


def test_settings_rejects_invalid_admin_emails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "development")
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "bad-email")
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "ONFLOW_ADMIN_EMAILS" in str(exc.value)


def test_admin_emails_bootstrap_requires_verified_oauth_email(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops-bootstrap@onflow.test")
    monkeypatch.setenv("ONFLOW_GOOGLE_CLIENT_IDS", "web-id")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def _unverified(_t: str) -> dict:
        return {
            "sub": "admin-sub-1",
            "email": "ops-bootstrap@onflow.test",
            "email_verified": False,
        }

    monkeypatch.setattr("app.routers.oauth_signin.verify_google_id_token", _unverified)
    resp = client.post("/api/v1/auth/google", json={"id_token": "x" * 40})
    assert resp.status_code == 403
    assert "verified" in (resp.json().get("detail") or "").lower()


def test_admin_emails_bootstrap_promotes_verified_oauth_signin(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops-bootstrap@onflow.test")
    monkeypatch.setenv("ONFLOW_GOOGLE_CLIENT_IDS", "web-id")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def _verified(_t: str) -> dict:
        return {
            "sub": "admin-sub-2",
            "email": "ops-bootstrap@onflow.test",
            "email_verified": True,
        }

    monkeypatch.setattr("app.routers.oauth_signin.verify_google_id_token", _verified)
    resp = client.post("/api/v1/auth/google", json={"id_token": "y" * 40})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    user = client.app.state.db.get_user(body["user_id"])
    assert user is not None and user.is_admin

    from app.core.database import get_engine

    with Session(get_engine()) as session:
        events = session.exec(
            select(AdminRoleEventModel).where(AdminRoleEventModel.user_id == user.id)
        ).all()
    assert len(events) == 1
    assert events[0].event_type == "promoted"
    assert events[0].source == "oauth_google"
    assert events[0].email == "ops-bootstrap@onflow.test"

    r = client.get(
        "/api/v1/admin/share-stats?days=7",
        headers={"Authorization": f"Bearer {body['token']}"},
    )
    assert r.status_code == 200


def test_admin_emails_bootstrap_denied_for_unverified_email_session(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops-bootstrap@onflow.test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    resp = client.post(
        "/api/v1/auth/session",
        json={"email": "ops-bootstrap@onflow.test"},
    )
    assert resp.status_code == 200
    user = client.app.state.db.get_user(resp.json()["user_id"])
    assert user is not None
    assert not user.is_admin
