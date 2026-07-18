from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_engine
from app.models import ClipModel
from app.services.clip_pending_reaper import reap_abandoned_pending_clips


@pytest.mark.asyncio
async def test_reaper_deletes_old_pending_only(client: TestClient, tmp_path: Path) -> None:
    monkey_user = "reaper-user-1"
    upload_dir = Path(client.app.state.upload_dir)
    now = datetime.now(timezone.utc)

    old_key = f"clips/{monkey_user}/old.mp4"
    new_key = f"clips/{monkey_user}/new.mp4"
    for key in (old_key, new_key):
        p = upload_dir / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"clip")

    with Session(get_engine()) as db:
        db.add(
            ClipModel(
                id="old-pending",
                user_id=monkey_user,
                storage_key=old_key,
                storage_url="",
                upload_status="pending",
                created_at=now - timedelta(hours=48),
                updated_at=now - timedelta(hours=48),
            )
        )
        db.add(
            ClipModel(
                id="new-pending",
                user_id=monkey_user,
                storage_key=new_key,
                storage_url="",
                upload_status="pending",
                created_at=now - timedelta(minutes=5),
                updated_at=now - timedelta(minutes=5),
            )
        )
        db.commit()

    report = await reap_abandoned_pending_clips(
        storage=client.app.state.storage,
        older_than_hours=24,
    )
    assert report["deleted_rows"] >= 1
    assert not (upload_dir / old_key).exists()
    assert (upload_dir / new_key).exists()

    with Session(get_engine()) as db:
        assert db.get(ClipModel, "old-pending") is None
        assert db.get(ClipModel, "new-pending") is not None


@pytest.mark.asyncio
async def test_reaper_respects_config_hours(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_CLIP_PENDING_REAP_HOURS", "1")
    get_settings.cache_clear()
    report = await reap_abandoned_pending_clips(
        storage=client.app.state.storage,
        older_than_hours=None,
        limit=10,
    )
    assert report["older_than_hours"] == 1
