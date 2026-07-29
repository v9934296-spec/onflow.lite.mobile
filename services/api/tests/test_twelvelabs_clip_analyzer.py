"""Mocked Twelve Labs Pegasus main analysis adapter."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.schemas.gemini_analysis import GeminiClipAnalysis
from app.services.gemini_pipeline_error import GeminiPipelineError
from app.services.gemini_prompt import ClipAnalysisMetadata
from app.services.twelvelabs_clip_analyzer import analyze_clip_with_twelvelabs
from tests.test_gemini_prompt_pack import SAMPLE_GOOD


class _TextEvent:
    def __init__(self, text: str) -> None:
        self.event_type = "text_generation"
        self.text = text


@pytest.mark.asyncio
async def test_analyze_clip_missing_key_raises_not_configured(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    cfg = Settings(twelvelabs_api_key="")
    meta = ClipAnalysisMetadata.all_unknown()
    with pytest.raises(GeminiPipelineError) as ei:
        await analyze_clip_with_twelvelabs(str(clip), meta, settings=cfg)
    assert ei.value.reason == "twelvelabs_not_configured"


@pytest.mark.asyncio
async def test_analyze_clip_parses_streamed_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake-video")
    cfg = Settings(twelvelabs_api_key="test-key", twelvelabs_model="pegasus1.5")
    meta = ClipAnalysisMetadata.all_unknown()
    raw_json = json.dumps(SAMPLE_GOOD)

    mock_client = MagicMock()
    mock_asset = MagicMock()
    mock_asset.id = "asset-abc123"
    mock_client.assets.create.return_value = mock_asset
    ready_asset = MagicMock()
    ready_asset.status = "ready"
    mock_client.assets.retrieve.return_value = ready_asset
    mock_client.analyze_stream.return_value = [_TextEvent(raw_json)]

    with patch("app.services.twelvelabs_clip_analyzer.TwelveLabs", return_value=mock_client):
        parsed, asset_id = await analyze_clip_with_twelvelabs(
            str(clip),
            meta,
            settings=cfg,
            job_id="job-1",
            account_tier="pro",
        )

    assert asset_id == "asset-abc123"
    assert isinstance(parsed, GeminiClipAnalysis)
    assert parsed.review_summary == SAMPLE_GOOD["review_summary"]
    mock_client.assets.create.assert_called_once()
    mock_client.analyze_stream.assert_called()
