from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_engine
from app.models import ClipJobModel, ClipModel


@pytest.fixture(autouse=True)
def _default_clip_abuse_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests assert the configured abuse caps — override suite-wide generous defaults."""
    monkeypatch.setenv("ONFLOW_CLIP_RATE_LIMIT_PER_HOUR", "10")
    monkeypatch.setenv("ONFLOW_CLIP_RATE_LIMIT_PER_DAY", "30")
    get_settings.cache_clear()


def _seed_jobs(user_id: str, count: int, *, hours_ago: float) -> None:
    now = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    with Session(get_engine()) as session:
        for i in range(count):
            session.add(
                ClipJobModel(
                    id=f"seed_{user_id}_{hours_ago}_{i}",
                    user_id=user_id,
                    status="completed",
                    created_at=now,
                    updated_at=now,
                    input_reference="storage:seed.mp4",
                    clip_label="seed",
                    tier="free",
                    quota_source="monthly",
                    metadata_json="{}",
                )
            )
        session.commit()


def _post_clip_dev(client, idx: int) -> int:
    response = client.post(
        "/api/v1/clips/initiate-upload",
        json={
            "duration_seconds": 4.5,
            "width_px": 1080,
            "height_px": 1920,
            "content_type": "video/mp4",
            "size_bytes": 1024 + idx,
        },
    )
    return response.status_code


def test_daily_cap_blocks_over_configured_daily(authed_client) -> None:
    """Abuse daily cap (Settings.clip_rate_limit_per_day), not monthly product quota."""
    user_id = "test-user-001"
    _seed_jobs(user_id, 30, hours_ago=2)
    status = _post_clip_dev(authed_client, 1)
    assert status == 429


def test_hourly_cap_blocks_over_configured_hourly(authed_client) -> None:
    user_id = "test-user-001"
    _seed_jobs(user_id, 10, hours_ago=0.2)
    status = _post_clip_dev(authed_client, 2)
    assert status == 429


def test_old_clips_do_not_count_toward_daily_cap(authed_client) -> None:
    user_id = "test-user-001"
    _seed_jobs(user_id, 50, hours_ago=30)
    status = _post_clip_dev(authed_client, 3)
    assert status == 201
    with Session(get_engine()) as session:
        created = session.exec(
            select(ClipModel)
            .where(ClipModel.user_id == user_id)
            .order_by(ClipModel.created_at.desc())
        ).first()
    assert created is not None
