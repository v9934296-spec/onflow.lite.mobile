"""Deep health clip queue metrics."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_health_deep_includes_clip_queue_metrics(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-placeholder-key-not-used-in-request")
    r = client.get("/health/deep")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    cq = body.get("clip_queue")
    assert isinstance(cq, dict)
    assert "queue_depth" in cq
    assert "processing_count" in cq
    assert "oldest_pending_age_seconds" in cq
    assert isinstance(cq.get("queue_configured"), bool)
    assert isinstance(cq.get("worker_expected"), bool)
    assert int(cq["queue_depth"]) >= 0
    assert int(cq["processing_count"]) >= 0
    opa = cq["oldest_pending_age_seconds"]
    assert opa is None or (isinstance(opa, int) and opa >= 0)
