"""BE-002 — a skater is only charged when a usable analysis comes back.

Spec decision 17. Before this, a job that reached Gemini or Pegasus and then
failed kept the charge: the skater paid for a non-answer. These tests pin the
reserve / finalize / release contract, including its idempotency.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.clip_job import ClipJobRecord
from app.services.clip_quota import begin_quota_release
from tests.conftest import wait_for_terminal_job


def _job(quota_source: str | None) -> ClipJobRecord:
    return ClipJobRecord.new_pending(
        "j-quota", "u-quota", "storage:k.mp4", quota_source=quota_source
    )


# --------------------------------------------------------------------------
# Release primitive
# --------------------------------------------------------------------------


def test_monthly_charge_is_released_by_the_marker_alone() -> None:
    job = _job("monthly")
    release = begin_quota_release(job)
    assert release.changed is True
    assert release.refund_bonus is False
    assert job.quota_source == "monthly_refunded"


def test_bonus_charge_requires_settling_the_credit() -> None:
    job = _job("bonus")
    release = begin_quota_release(job)
    assert release.changed is True
    assert release.refund_bonus is True
    assert job.quota_source == "bonus_refunded"


def test_legacy_null_quota_source_is_treated_as_monthly() -> None:
    job = _job(None)
    release = begin_quota_release(job)
    assert release.changed is True
    assert job.quota_source == "monthly_refunded"


def test_unlimited_tier_has_no_charge_to_release() -> None:
    job = _job("unlimited")
    release = begin_quota_release(job)
    assert release.changed is False
    assert release.refund_bonus is False
    assert job.quota_source == "unlimited"


@pytest.mark.parametrize("source", ["monthly", "bonus"])
def test_release_is_idempotent(source: str) -> None:
    """A retried worker, or two workers racing, must not refund twice."""
    job = _job(source)
    first = begin_quota_release(job)
    assert first.changed is True

    second = begin_quota_release(job)
    assert second.changed is False
    assert second.refund_bonus is False

    third = begin_quota_release(job)
    assert third.changed is False


# --------------------------------------------------------------------------
# End-to-end through the worker
# --------------------------------------------------------------------------

READABLE_FIRST_PASS: dict[str, Any] = {
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
}


def _free_user(client: TestClient, email: str) -> tuple[str, dict[str, str]]:
    r = client.post("/api/v1/auth/session", json={"email": email})
    assert r.status_code == 200, r.text
    user_id = r.json()["user_id"]
    headers = {"Authorization": f"Bearer {r.json()['session_token']}"}
    # Force free tier so the submission charges monthly quota, not trial unlimited.
    client.app.state.db.ensure_invite_claim_user(user_id, "free")
    return user_id, headers


def _submit(client: TestClient, headers: dict[str, str]) -> str:
    from app.services.video_signature import MINIMAL_VIDEO_SNIFF_BYTES

    init = client.post(
        "/api/v1/clips/initiate-upload",
        headers=headers,
        json={
            "duration_seconds": 4.0,
            "width_px": 1080,
            "height_px": 1920,
            "content_type": "video/mp4",
            "size_bytes": max(len(MINIMAL_VIDEO_SNIFF_BYTES), 1),
        },
    )
    assert init.status_code == 201, init.text
    body = init.json()
    dest = Path(client.app.state.upload_dir) / body["storage_key"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(MINIMAL_VIDEO_SNIFF_BYTES)

    complete = client.post(
        f"/api/v1/clips/{body['clip_id']}/complete-upload", headers=headers
    )
    assert complete.status_code == 200, complete.text
    return body["clip_id"]


def _readable(monkeypatch: pytest.MonkeyPatch, readiness: str = "usable") -> None:
    from app.services import clip_worker

    payload = {**READABLE_FIRST_PASS, "review_readiness": readiness}
    monkeypatch.setattr(
        clip_worker, "analyze_video_first_pass", lambda _path: dict(payload)
    )


def test_unreadable_footage_releases_the_charge(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit policy: footage we could not read is not billed."""
    user_id, headers = _free_user(client, "unreadable-quota@onflow.test")
    clip_id = _submit(client, headers)

    terminal = wait_for_terminal_job(client, clip_id, headers)
    assert terminal["status"] == "failed", terminal
    assert terminal["failure_reason"] == "video_unreadable"

    job = client.app.state.repo.get(clip_id)
    assert job is not None
    assert job.quota_source == "monthly_refunded"
    assert client.app.state.repo.count_monthly_free_jobs(user_id) == 0


def test_provider_failure_releases_the_charge(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A job that reached the provider and came back empty must not be billed."""
    from app.services import clip_worker
    from app.services.gemini_pipeline_error import GeminiPipelineError

    _readable(monkeypatch)

    async def _provider_down(*_a: object, **_k: object) -> None:
        raise GeminiPipelineError("provider_unavailable", "upstream 503")

    monkeypatch.setattr(clip_worker, "analyze_clip_with_gemini", _provider_down)

    user_id, headers = _free_user(client, "provider-down@onflow.test")
    clip_id = _submit(client, headers)

    terminal = wait_for_terminal_job(client, clip_id, headers)
    assert terminal["status"] == "completed", terminal
    assert terminal["result"]["review_readiness"] == "insufficient"

    job = client.app.state.repo.get(clip_id)
    assert job is not None
    assert job.quota_source == "monthly_refunded"
    assert client.app.state.repo.count_monthly_free_jobs(user_id) == 0


def test_internal_error_releases_the_charge(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import clip_worker

    def _boom(_path: str) -> dict[str, Any]:
        raise RuntimeError("first pass exploded")

    monkeypatch.setattr(clip_worker, "analyze_video_first_pass", _boom)

    user_id, headers = _free_user(client, "internal-error@onflow.test")
    clip_id = _submit(client, headers)

    terminal = wait_for_terminal_job(client, clip_id, headers)
    assert terminal["status"] == "failed", terminal
    assert terminal["failure_reason"] == "internal_error"

    job = client.app.state.repo.get(clip_id)
    assert job is not None
    assert job.quota_source == "monthly_refunded"
    assert client.app.state.repo.count_monthly_free_jobs(user_id) == 0


def test_usable_analysis_keeps_the_charge(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of the contract: a real read is finalized, not refunded."""
    _readable(monkeypatch, readiness="usable")

    user_id, headers = _free_user(client, "usable-quota@onflow.test")
    clip_id = _submit(client, headers)

    terminal = wait_for_terminal_job(client, clip_id, headers)
    assert terminal["status"] == "completed", terminal
    assert terminal["result"]["review_readiness"] == "usable"

    job = client.app.state.repo.get(clip_id)
    assert job is not None
    assert job.quota_source == "monthly"
    assert client.app.state.repo.count_monthly_free_jobs(user_id) == 1


def test_limited_analysis_keeps_the_charge(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A limited read still tells the skater something, so it is billable."""
    _readable(monkeypatch, readiness="limited")

    user_id, headers = _free_user(client, "limited-quota@onflow.test")
    clip_id = _submit(client, headers)

    terminal = wait_for_terminal_job(client, clip_id, headers)
    assert terminal["status"] == "completed", terminal
    assert terminal["result"]["review_readiness"] == "limited"

    job = client.app.state.repo.get(clip_id)
    assert job is not None
    assert job.quota_source == "monthly"
    assert client.app.state.repo.count_monthly_free_jobs(user_id) == 1


def test_released_bonus_credit_is_returned_to_the_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bonus credit spent on a failed analysis comes back to the account."""
    from app.core.config import get_settings

    monkeypatch.setenv("ONFLOW_RATE_LIMIT_FREE", "0")
    get_settings.cache_clear()

    user_id, headers = _free_user(client, "bonus-refund@onflow.test")
    identity = client.app.state.db

    # Burn the single monthly slot so the next submission reaches the bonus pool.
    first = _submit(client, headers)
    wait_for_terminal_job(client, first, headers)
    burned = client.app.state.repo.get(first)
    assert burned is not None and burned.quota_source == "monthly_refunded"

    # A refunded monthly row is not counted, so grant bonus and force the
    # monthly cap to be already consumed by a chargeable row.
    now = datetime.now(timezone.utc)
    client.app.state.repo.create(
        ClipJobRecord(
            id="holds-the-monthly-slot",
            user_id=user_id,
            status="completed",
            created_at=now,
            updated_at=now,
            input_reference="storage:x.mp4",
            failure_reason=None,
            result_json={"review_readiness": "usable"},
            clip_label="x",
            tier="free",
            clip_metadata={},
            quota_source="monthly",
        )
    )
    identity.add_bonus_analyses(user_id, 1)
    before = client.get("/api/v1/account/quota", headers=headers).json()

    clip_id = _submit(client, headers)
    charged = client.app.state.repo.get(clip_id)
    assert charged is not None
    assert charged.quota_source == "bonus", charged.quota_source

    wait_for_terminal_job(client, clip_id, headers)

    released = client.app.state.repo.get(clip_id)
    assert released is not None
    assert released.quota_source == "bonus_refunded"

    after = client.get("/api/v1/account/quota", headers=headers).json()
    assert after["bonus_analyses"] == before["bonus_analyses"], (before, after)
