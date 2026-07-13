"""P.T.E. Tech 1.0 — Custom Lines tests."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_line(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/api/v1/lines",
        json={
            "line_name": "Park combo",
            "trick_sequence": ["kickflip", "50-50", "heelflip"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["line_name"] == "Park combo"
    assert data["trick_sequence"] == ["kickflip", "50-50", "heelflip"]
    assert data["total_attempts"] == 0


def test_create_line_min_2_tricks(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/api/v1/lines",
        json={
            "line_name": "Too short",
            "trick_sequence": ["kickflip"],
        },
    )
    assert r.status_code == 422


def test_list_lines_lazy_seeds_example_when_none(authed_client: TestClient) -> None:
    r = authed_client.get("/api/v1/lines")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["line_name"] == "Example: ollie → kickflip"


def test_list_lines_with_data(authed_client: TestClient) -> None:
    authed_client.post(
        "/api/v1/lines",
        json={"line_name": "Line A", "trick_sequence": ["ollie", "kickflip"]},
    )
    authed_client.post(
        "/api/v1/lines",
        json={"line_name": "Line B", "trick_sequence": ["heelflip", "manual"]},
    )
    r = authed_client.get("/api/v1/lines")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_line_detail(authed_client: TestClient) -> None:
    cr = authed_client.post(
        "/api/v1/lines",
        json={"line_name": "Test line", "trick_sequence": ["kickflip", "boardslide"]},
    )
    line_id = cr.json()["line_id"]
    r = authed_client.get(f"/api/v1/lines/{line_id}")
    assert r.status_code == 200
    assert r.json()["line_name"] == "Test line"
    assert "attempts" in r.json()


def test_update_line(authed_client: TestClient) -> None:
    cr = authed_client.post(
        "/api/v1/lines",
        json={"line_name": "Old name", "trick_sequence": ["ollie", "kickflip"]},
    )
    line_id = cr.json()["line_id"]
    r = authed_client.put(f"/api/v1/lines/{line_id}", json={"line_name": "New name"})
    assert r.status_code == 200
    assert r.json()["line_name"] == "New name"


def test_delete_line(authed_client: TestClient) -> None:
    cr = authed_client.post(
        "/api/v1/lines",
        json={"line_name": "Delete me", "trick_sequence": ["ollie", "kickflip"]},
    )
    line_id = cr.json()["line_id"]
    r = authed_client.delete(f"/api/v1/lines/{line_id}")
    assert r.status_code == 200
    r2 = authed_client.get(f"/api/v1/lines/{line_id}")
    assert r2.status_code == 404


def test_line_not_found(authed_client: TestClient) -> None:
    r = authed_client.get("/api/v1/lines/nonexistent")
    assert r.status_code == 404


def test_record_line_attempt(authed_client: TestClient) -> None:
    cr = authed_client.post(
        "/api/v1/lines",
        json={"line_name": "Attempt line", "trick_sequence": ["kickflip", "manual"]},
    )
    line_id = cr.json()["line_id"]
    r = authed_client.post(f"/api/v1/lines/{line_id}/attempts?job_id=job123&landed=yes")
    assert r.status_code == 200
    assert r.json()["landed"] == "yes"
    assert r.json()["job_id"] == "job123"

    detail = authed_client.get(f"/api/v1/lines/{line_id}")
    assert detail.json()["total_attempts"] == 1
    assert detail.json()["landed"] == 1


def test_create_line_max_4_tricks(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/api/v1/lines",
        json={
            "line_name": "Too long",
            "trick_sequence": ["ollie", "kickflip", "heelflip", "manual", "treflip"],
        },
    )
    assert r.status_code == 422


def test_create_line_exactly_4_tricks(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/api/v1/lines",
        json={
            "line_name": "Max line",
            "trick_sequence": ["ollie", "kickflip", "heelflip", "manual"],
        },
    )
    assert r.status_code == 200
    assert len(r.json()["trick_sequence"]) == 4
