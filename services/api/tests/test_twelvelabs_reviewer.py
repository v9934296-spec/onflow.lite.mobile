"""Mocked Twelve Labs Pegasus enrichment adapter."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.twelvelabs_reviewer import TwelveLabsReviewer


class _TextEvent:
    def __init__(self, text: str) -> None:
        self.event_type = "text_generation"
        self.text = text


@pytest.mark.asyncio
async def test_enrich_reuses_asset_id_and_parses_json() -> None:
    payload = {
        "review_addendum": "Landing looked controlled.",
        "observation_bullets": ["Weight stayed centered."],
        "coaching": {
            "body_position": "Stay compact through the trick.",
            "foot_placement": None,
            "timing": None,
            "board_control": None,
            "commitment": None,
            "balance": "Absorb with ankles on landing.",
            "style_notes": None,
            "improvement_drill": None,
        },
        "landed": "yes",
    }
    mock_client = MagicMock()
    mock_client.analyze_stream.return_value = [_TextEvent(json.dumps(payload))]

    settings = Settings(twelvelabs_api_key="test-key", twelvelabs_model="pegasus1.5")
    reviewer = TwelveLabsReviewer(settings)

    with patch("app.services.twelvelabs_reviewer.TwelveLabs", return_value=mock_client):
        out = await reviewer.enrich(
            asset_id="asset-xyz",
            clip_label="kickflip",
            clip_metadata={"tricks": ["kickflip"], "stance": "regular"},
            user_id="user-1",
        )

    assert out["landed"] == "yes"
    assert out["review_addendum"] == "Landing looked controlled."
    mock_client.analyze_stream.assert_called_once()
    call_kwargs = mock_client.analyze_stream.call_args.kwargs
    assert call_kwargs["model_name"] == "pegasus1.5"
    video_ctx = call_kwargs["video"]
    assert getattr(video_ctx, "asset_id", None) == "asset-xyz"


def test_reviewer_requires_api_key() -> None:
    with pytest.raises(ValueError, match="Twelve Labs API key"):
        TwelveLabsReviewer(Settings(twelvelabs_api_key=""))
