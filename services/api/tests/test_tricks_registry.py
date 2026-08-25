"""BE-005 — canonical trick catalog is served from the server registry."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.trick_registry import TRICK_REGISTRY, get_all_canonical_names


def test_tricks_requires_auth(client: TestClient) -> None:
    r = client.get("/api/v1/tricks")
    assert r.status_code in (401, 403)


def test_tricks_matches_in_process_registry(client: TestClient) -> None:
    token = client.post(
        "/api/v1/auth/session", json={"email": "tricks@onflow.test"}
    ).json()["session_token"]
    r = client.get("/api/v1/tricks", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    tricks = r.json()["tricks"]
    names = {t["name"] for t in tricks}
    assert names == set(get_all_canonical_names())
    assert len(tricks) == len(TRICK_REGISTRY)
    kickflip = next(t for t in tricks if t["name"] == "Kickflip")
    assert kickflip["id"] == "kickflip"
    assert kickflip["category"]
    assert isinstance(kickflip["aliases"], list)
    assert isinstance(kickflip["difficulty_tier"], int)
