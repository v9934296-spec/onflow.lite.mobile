from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    submit_clip_via_presigned,
    wait_for_terminal_job,
    write_presigned_upload,
)


def test_claim_endpoint_removed(client: TestClient) -> None:
    r = client.post("/api/v1/auth/claim", json={"code": "grind-01"})
    assert r.status_code == 404


def test_clip_submission_monthly_quota_exceeded_returns_429(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fourth complete-upload is 429 only after three chargeable monthly slots.

    Unreadable sniff bytes refund ``monthly`` (BE-002). This fixture stubs a
    usable first pass and waits for terminal jobs so the cap is actually occupied.
    """
    monkeypatch.setenv("ONFLOW_DATABASE_PATH", str(tmp_path / "onflow.db"))
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ONFLOW_RATE_LIMIT_FREE", "3")
    import app.core.database as database_module
    from app.core.config import get_settings
    from app.services import clip_worker

    database_module._engine = None
    get_settings.cache_clear()
    monkeypatch.setattr(
        clip_worker,
        "analyze_video_first_pass",
        lambda _path: {
            "video_readable": True,
            "duration_seconds": 4.0,
            "fps": 30.0,
            "frame_count_estimated": 120,
            "frames_sampled": 12,
            "motion_detected": True,
            "mean_brightness_0_1": 0.5,
            "laplacian_var_mean": 140.0,
            "review_readiness": "usable",
            "observations": ["Rider visible across sampled frames."],
            "processing_notes": [],
            "review_summary_base": "Clip is readable.",
        },
    )
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/session", json={"email": "rate-limit@onflow.test"})
        assert r.status_code == 200
        user_id = r.json()["user_id"]
        c.app.state.db.set_user_tier(user_id, "free")
        from app.services.video_signature import MINIMAL_VIDEO_SNIFF_BYTES

        h = {"Authorization": f"Bearer {r.json()['session_token']}"}
        occupied = [
            submit_clip_via_presigned(c, h, video_bytes=MINIMAL_VIDEO_SNIFF_BYTES)
            for _ in range(3)
        ]
        for clip_id in occupied:
            terminal = wait_for_terminal_job(c, clip_id, h)
            assert terminal["status"] == "completed", terminal
            job = c.app.state.repo.get(clip_id)
            assert job is not None
            assert job.quota_source == "monthly"
        assert c.app.state.repo.count_monthly_free_jobs(user_id) == 3

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
        write_presigned_upload(c, initiated.json()["storage_key"], MINIMAL_VIDEO_SNIFF_BYTES)
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
