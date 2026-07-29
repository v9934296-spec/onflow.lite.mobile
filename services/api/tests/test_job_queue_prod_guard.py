"""Tier 3 hardening: clip analysis must never run in-process in production."""
from __future__ import annotations

import asyncio

import pytest

from app.services import job_queue


class _StubSettings:
    redis_url = ""
    is_production = True


def test_enqueue_refuses_in_process_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(job_queue, "_arq_pool", None, raising=False)
    monkeypatch.setattr(job_queue, "get_settings", lambda: _StubSettings())

    with pytest.raises(RuntimeError, match="ONFLOW_REDIS_URL is required in production"):
        asyncio.run(job_queue.enqueue_clip_job("job-1", "storage/key.mp4", "user-1"))
