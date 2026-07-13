from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import submit_clip_via_presigned


def _headers_for_email(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/session", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def test_export_requires_auth(client: TestClient) -> None:
    r = client.get("/api/v1/account/export")
    assert r.status_code == 401


def test_export_shape_and_consent_events(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.post(
        "/api/v1/consent/grant",
        headers=auth_headers,
        json={"copy_version": "v1_2026_04_14"},
    )
    r = client.get("/api/v1/account/export", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) >= {
        "user",
        "consent",
        "clips",
        "consent_events",
        "export_generated_at",
        "policy_version_at_export",
    }
    assert body["policy_version_at_export"] == "v1_2026_04_14"
    assert isinstance(body["export_generated_at"], str) and body["export_generated_at"]
    assert body["user"]["id"]
    assert body["consent"]["granted"] is True
    assert any(
        e.get("copy_version") == "v1_2026_04_14" for e in body["consent_events"]
    )


def test_export_includes_user_clips_only(
    client: TestClient, sample_valid_mp4_bytes: bytes
) -> None:
    ha = _headers_for_email(client, "export-a@onflow.test")
    hb = _headers_for_email(client, "export-b@onflow.test")
    job_a = submit_clip_via_presigned(client, ha, video_bytes=sample_valid_mp4_bytes)

    er_a = client.get("/api/v1/account/export", headers=ha)
    assert er_a.status_code == 200
    clip_ids_a = {c["job_id"] for c in er_a.json()["clips"]}
    assert job_a in clip_ids_a

    er_b = client.get("/api/v1/account/export", headers=hb)
    assert er_b.status_code == 200
    clip_ids_b = {c["job_id"] for c in er_b.json()["clips"]}
    assert job_a not in clip_ids_b
