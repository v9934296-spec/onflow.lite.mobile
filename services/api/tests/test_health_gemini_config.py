"""Health reflects Gemini key; missing key yields controlled analyzer failure (see test_api_contract.test_health for false)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services.gemini_clip_analyzer import GeminiPipelineError, analyze_clip_with_gemini
from app.services.gemini_prompt import ClipAnalysisMetadata


def test_health_reports_gemini_configured_when_key_set(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-placeholder-key-not-used-in-request")
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json().get("gemini_configured") is True


def test_health_reports_twelvelabs_and_clip_review_ready(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "tl-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("twelvelabs_configured") is True
    assert body.get("clip_review_ready") is True


@pytest.mark.asyncio
async def test_analyze_clip_missing_key_raises_not_configured_not_bare_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Degraded path: no API key → controlled failure reason, not an unhandled crash."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ONFLOW_GEMINI_API_KEY", raising=False)
    cfg = Settings(gemini_api_key="")
    assert not (cfg.gemini_api_key or "").strip()
    meta = ClipAnalysisMetadata.all_unknown()
    with pytest.raises(GeminiPipelineError) as ei:
        await analyze_clip_with_gemini("/any/path.mp4", meta, settings=cfg)
    assert ei.value.reason == "gemini_not_configured"
