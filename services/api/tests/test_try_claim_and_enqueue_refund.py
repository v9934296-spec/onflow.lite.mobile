"""CAS job claim + enqueue-failure quota refund."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.domain.clip_job import ClipJobRecord
from app.repositories.clip_jobs import InMemoryClipJobRepository


def test_try_claim_pending_to_processing_once() -> None:
    repo = InMemoryClipJobRepository()
    job = ClipJobRecord.new_pending("j1", "u1", "storage:k.mp4", quota_source="monthly")
    repo.create(job)

    first = repo.try_claim_for_processing("j1")
    assert first is not None
    assert first.status == "processing"
    assert first.claim_token
    assert first.lease_expires_at is not None

    # Second claim while lease is live: exclusive — other worker must skip.
    second = repo.try_claim_for_processing("j1")
    assert second is None


def test_try_claim_reclaims_stale_processing() -> None:
    from datetime import timedelta

    repo = InMemoryClipJobRepository()
    job = ClipJobRecord.new_pending("j-stale", "u1", "storage:k.mp4")
    repo.create(job)
    claimed = repo.try_claim_for_processing("j-stale")
    assert claimed is not None
    first_token = claimed.claim_token

    # Expire the lease so reclaim is allowed.
    claimed.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    repo.update(claimed)

    reclaimed = repo.try_claim_for_processing("j-stale")
    assert reclaimed is not None
    assert reclaimed.status == "processing"
    assert reclaimed.claim_token != first_token
    assert reclaimed.attempt_number >= 2


def test_update_claimed_rejects_stale_token() -> None:
    from copy import deepcopy

    repo = InMemoryClipJobRepository()
    job = ClipJobRecord.new_pending("j-fence", "u1", "storage:k.mp4")
    repo.create(job)
    claimed = repo.try_claim_for_processing("j-fence")
    assert claimed is not None
    token = claimed.claim_token
    assert token

    payload = deepcopy(claimed)
    payload.with_status("completed", result_json={"ok": True})
    assert repo.update_claimed(payload, claim_token="wrong-token") is False
    still = repo.get("j-fence")
    assert still is not None
    assert still.status == "processing"

    assert repo.update_claimed(payload, claim_token=token) is True
    done = repo.get("j-fence")
    assert done is not None
    assert done.status == "completed"


def test_renew_lease_extends_ownership() -> None:
    from datetime import timedelta

    repo = InMemoryClipJobRepository()
    job = ClipJobRecord.new_pending("j-hb", "u1", "storage:k.mp4")
    repo.create(job)
    claimed = repo.try_claim_for_processing("j-hb")
    assert claimed is not None
    token = claimed.claim_token
    assert token

    near = datetime.now(timezone.utc) + timedelta(seconds=5)
    claimed.lease_expires_at = near
    repo.update(claimed)

    assert repo.renew_lease("j-hb", claim_token=token, lease_seconds=300) is True
    renewed = repo.get("j-hb")
    assert renewed is not None
    assert renewed.lease_expires_at is not None
    assert renewed.lease_expires_at > near

    assert repo.renew_lease("j-hb", claim_token="other", lease_seconds=300) is False


def test_null_lease_uses_soft_timeout() -> None:
    from datetime import timedelta

    from app.core.config import get_settings

    repo = InMemoryClipJobRepository()
    job = ClipJobRecord.new_pending("j-null", "u1", "storage:k.mp4")
    repo.create(job)
    claimed = repo.try_claim_for_processing("j-null")
    assert claimed is not None
    claimed.lease_expires_at = None
    claimed.updated_at = datetime.now(timezone.utc)
    repo.update(claimed)

    # Fresh NULL lease must not be reclaimable.
    assert repo.try_claim_for_processing("j-null") is None

    claimed.updated_at = datetime.now(timezone.utc) - timedelta(
        seconds=get_settings().arq_job_timeout + 1
    )
    repo.update(claimed)
    assert repo.try_claim_for_processing("j-null") is not None


def test_try_claim_skips_terminal() -> None:
    repo = InMemoryClipJobRepository()
    job = ClipJobRecord.new_pending("j2", "u1", "storage:k.mp4")
    job.with_status("completed", result_json={"ok": True})
    repo.create(job)
    assert repo.try_claim_for_processing("j2") is None


def test_monthly_refunded_not_counted_in_quota(client: TestClient) -> None:
    headers = {
        "Authorization": "Bearer "
        + client.post("/api/v1/auth/session", json={"email": "refund-q@onflow.test"}).json()[
            "session_token"
        ]
    }
    me = client.get("/api/v1/account/me", headers=headers).json()
    user_id = me["user_id"]
    repo = client.app.state.repo
    now = datetime.now(timezone.utc)
    repo.create(
        ClipJobRecord(
            id="refunded-1",
            user_id=user_id,
            status="failed",
            created_at=now,
            updated_at=now,
            input_reference="storage:x.mp4",
            failure_reason="enqueue_failed",
            result_json=None,
            clip_label="x",
            tier="free",
            clip_metadata={},
            quota_source="monthly_refunded",
        )
    )
    assert repo.count_monthly_free_jobs(user_id) == 0


def test_enqueue_failure_refunds_and_marks_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.services import clip_v1_pipeline

    async def _boom(*_a, **_k):
        raise RuntimeError("redis down")

    monkeypatch.setattr(clip_v1_pipeline, "enqueue_clip_job", _boom)

    r = client.post("/api/v1/auth/session", json={"email": "enq-fail@onflow.test"})
    assert r.status_code == 200
    user_id = r.json()["user_id"]
    headers = {"Authorization": f"Bearer {r.json()['session_token']}"}
    # Force free tier so reserve uses monthly quota (not trial unlimited).
    client.app.state.db.ensure_invite_claim_user(user_id, "free")

    init = client.post(
        "/api/v1/clips/initiate-upload",
        headers=headers,
        json={
            "duration_seconds": 3,
            "width_px": 1080,
            "height_px": 1920,
            "content_type": "video/mp4",
            "size_bytes": 12,
        },
    )
    assert init.status_code == 201, init.text
    body = init.json()
    clip_id = body["clip_id"]
    storage_key = body["storage_key"]

    from app.services.video_signature import MINIMAL_VIDEO_SNIFF_BYTES

    dest = Path(client.app.state.upload_dir) / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(MINIMAL_VIDEO_SNIFF_BYTES)

    complete = client.post(f"/api/v1/clips/{clip_id}/complete-upload", headers=headers)
    assert complete.status_code == 503, complete.text

    job = client.app.state.repo.get(clip_id)
    assert job is not None
    assert job.status == "failed"
    assert job.failure_reason == "enqueue_failed"
    assert job.quota_source == "monthly_refunded"
    assert client.app.state.repo.count_monthly_free_jobs(job.user_id) == 0
