"""
Twelve Labs Pegasus enrichment pass — reuses asset from main analysis.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from twelvelabs import TwelveLabs
from twelvelabs.types import AnalyzePromptV2, VideoContext_AssetId

from app.core.config import Settings, get_settings
from app.services.gemini_reviewer import (
    GEMINI_CALL_TIMEOUT_SECONDS,
    MAX_OUTPUT_TOKENS,
    _parse_enrichment_json,
)
from app.services.pegasus_prompt import build_pegasus_enrichment_prompt

logger = logging.getLogger(__name__)

_ENRICHMENT_MAX_TOKENS = MAX_OUTPUT_TOKENS


def _enrich_sync(
    *,
    api_key: str,
    asset_id: str,
    input_text: str,
    model_name: str,
    max_tokens: int,
) -> str:
    client = TwelveLabs(api_key=api_key)
    video = VideoContext_AssetId(type="asset_id", asset_id=asset_id)
    prompt = AnalyzePromptV2(input_text=input_text)
    chunks: list[str] = []
    for event in client.analyze_stream(
        model_name=model_name,
        video=video,
        prompt_v_2=prompt,
        max_tokens=max_tokens,
    ):
        if getattr(event, "event_type", None) == "text_generation":
            piece = getattr(event, "text", None)
            if isinstance(piece, str) and piece:
                chunks.append(piece)
    return "".join(chunks).strip()


class TwelveLabsReviewer:
    """Pegasus enrichment — same return shape as ``GeminiReviewer.enrich``."""

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        if not (cfg.twelvelabs_api_key or "").strip():
            raise ValueError("Twelve Labs API key is required. Set ONFLOW_TWELVELABS_API_KEY.")
        self._settings = cfg
        self._model = (cfg.twelvelabs_model or "pegasus1.5").strip()

    async def enrich(
        self,
        *,
        asset_id: str,
        clip_label: str,
        clip_metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        if not (asset_id or "").strip():
            raise ValueError("asset_id is required for Pegasus enrichment")

        prompt_pack = build_pegasus_enrichment_prompt(clip_label, clip_metadata)

        async def _call() -> str:
            return await asyncio.to_thread(
                _enrich_sync,
                api_key=self._settings.twelvelabs_api_key,
                asset_id=asset_id.strip(),
                input_text=prompt_pack.input_text,
                model_name=self._model,
                max_tokens=_ENRICHMENT_MAX_TOKENS,
            )

        try:
            raw_text = await asyncio.wait_for(_call(), timeout=GEMINI_CALL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError as exc:
            logger.warning(
                "twelvelabs_enrichment_timeout clip_label=%s user_id=%s",
                clip_label,
                user_id,
            )
            raise RuntimeError("Pegasus enrichment timed out") from exc

        logger.info(
            "twelvelabs_enrichment_complete clip_label=%s user_id=%s len=%d",
            clip_label,
            user_id,
            len(raw_text),
        )
        return _parse_enrichment_json(raw_text)
