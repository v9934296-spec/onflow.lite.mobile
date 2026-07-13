from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_consent_requires_auth(client: TestClient) -> None:
    r = client.get("/api/v1/consent")
    assert r.status_code == 401


def test_consent_not_granted_until_post(client: TestClient, auth_headers: dict[str, str]) -> None:
    r = client.get("/api/v1/consent", headers=auth_headers)
    assert r.status_code == 200
    b = r.json()
    assert b["granted"] is False
    assert b["granted_at"] is None


def test_consent_grant_and_status(client: TestClient, auth_headers: dict[str, str]) -> None:
    r = client.post(
        "/api/v1/consent/grant",
        headers=auth_headers,
        json={"copy_version": "v1_2026_04_14"},
    )
    assert r.status_code == 200, r.text
    st = r.json()["status"]
    assert st["granted"] is True
    assert st["copy_version"] == "v1_2026_04_14"

    r2 = client.get("/api/v1/consent", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["granted"] is True


def test_me_includes_consent(client: TestClient, auth_headers: dict[str, str]) -> None:
    r = client.get("/api/v1/account/me", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "consent" in body
    assert body["consent"]["granted"] in (True, False)
