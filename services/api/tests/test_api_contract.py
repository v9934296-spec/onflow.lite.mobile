from __future__ import annotations

import time

from fastapi.testclient import TestClient

from tests.conftest import submit_clip_via_presigned, wait_for_terminal_job


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body.get("gemini_configured"), bool)
    assert body.get("gemini_configured") is False
    assert isinstance(body.get("twelvelabs_configured"), bool)
    assert body.get("twelvelabs_configured") is False
    assert isinstance(body.get("clip_review_ready"), bool)
    assert body.get("clip_review_ready") is False


def test_initiate_upload_requires_auth(client: TestClient) -> None:
    r = client.post(
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


def test_presigned_upload_returns_job_id(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    job_id = submit_clip_via_presigned(client, auth_headers)
    assert len(job_id) == 36


def test_get_job_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    r = client.get(
        "/api/v1/clips/jobs/00000000-0000-4000-8000-000000000000",
        headers=auth_headers,
    )
    assert r.status_code == 404


def test_status_lifecycle_shape(
    client: TestClient, auth_headers: dict[str, str], sample_valid_mp4_bytes: bytes
) -> None:
    job_id = submit_clip_via_presigned(
        client,
        auth_headers,
        video_bytes=sample_valid_mp4_bytes,
        client_hint_trick_id="session-a",
    )
    last = wait_for_terminal_job(client, job_id, auth_headers)

    assert last.get("status") == "completed", last
    assert last["job_id"] == job_id
    assert last.get("updated_at")
    assert "result" in last
    res = last["result"]
    assert res.get("analysis_type") == "skate_clip_review"
    assert res.get("schema_version") == 1
    assert res["clip_label"] == "session-a"
    assert isinstance(res.get("review_summary"), str)
    assert res.get("review_readiness") in ("usable", "limited", "insufficient")
    qs = res.get("quality_signals")
    assert isinstance(qs, dict)
    assert qs.get("video_readable") is True
    assert isinstance(qs.get("frames_sampled"), int)
    assert "motion_detected" in qs
    obs = res.get("observations")
    assert isinstance(obs, list)
    assert all(isinstance(x, str) for x in obs)
    notes = res.get("processing_notes")
    assert isinstance(notes, list)
    un = res.get("uncertainty_notes")
    assert isinstance(un, list)
    assert all(isinstance(x, str) for x in un)
    assert "confidence" not in res
    assert "trick_name" not in res
    nr = res.get("normalized_review")
    assert isinstance(nr, dict)
    assert nr.get("model") == "gemini"
    assert isinstance(nr.get("summary"), str)


def test_non_video_upload_fails_video_unreadable(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    job_id = submit_clip_via_presigned(
        client,
        auth_headers,
        video_bytes=b"not-a-real-video-but-nonempty",
    )
    last = wait_for_terminal_job(client, job_id, auth_headers, timeout_s=10.0)

    assert last.get("status") == "failed"
    assert last.get("failure_reason") == "video_unreadable"


def test_empty_upload_fails_job_with_video_unreadable(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    job_id = submit_clip_via_presigned(client, auth_headers, video_bytes=b"")
    last = wait_for_terminal_job(client, job_id, auth_headers, timeout_s=10.0)

    assert last.get("status") == "failed"
    assert last.get("failure_reason") == "video_unreadable"


def test_default_clip_label_is_untagged(
    client: TestClient, auth_headers: dict[str, str], sample_valid_mp4_bytes: bytes
) -> None:
    job_id = submit_clip_via_presigned(client, auth_headers, video_bytes=sample_valid_mp4_bytes)
    last = wait_for_terminal_job(client, job_id, auth_headers)

    assert last.get("status") == "completed"
    assert last["result"]["clip_label"] == "untagged"


def test_create_job_with_metadata(
    client: TestClient, auth_headers: dict[str, str], sample_valid_mp4_bytes: bytes
) -> None:
    job_id = submit_clip_via_presigned(
        client,
        auth_headers,
        video_bytes=sample_valid_mp4_bytes,
        client_hint_trick_id="kickflip",
    )
    last = wait_for_terminal_job(client, job_id, auth_headers)

    assert last.get("status") == "completed"
    assert last["result"]["clip_label"] == "kickflip"


def test_review_readiness_normalized(
    client: TestClient, auth_headers: dict[str, str], sample_valid_mp4_bytes: bytes
) -> None:
    job_id = submit_clip_via_presigned(client, auth_headers, video_bytes=sample_valid_mp4_bytes)
    last = wait_for_terminal_job(client, job_id, auth_headers)
    assert last["status"] == "completed"
    rr = last["result"]["review_readiness"]
    assert rr in ("usable", "limited", "insufficient")
