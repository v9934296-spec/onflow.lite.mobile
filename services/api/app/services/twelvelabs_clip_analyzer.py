"""
Twelve Labs Pegasus clip analysis — Pro tier main review pass.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from twelvelabs import TwelveLabs
from twelvelabs.types import AnalyzePromptV2, VideoContext_AssetId

from app.core.config import Settings, get_settings
from app.schemas.gemini_analysis import GeminiClipAnalysis
from app.services.expected_mechanics_gate import apply_expected_mechanics_gate
from app.services.gemini_analysis_parse import (
    PARSE_RETRY_REASONS,
    parse_gemini_clip_analysis_dict,
    validate_gemini_clip_analysis,
)
from app.services.gemini_output_quality import UsefulnessRejected, validate_usefulness
from app.services.gemini_pipeline_error import GeminiPipelineError
from app.services.gemini_prompt import ClipAnalysisMetadata
from app.services.pegasus_prompt import build_pegasus_clip_analysis_prompt

logger = logging.getLogger(__name__)

_ASSET_POLL_INTERVAL_S = 1.0
_ASSET_POLL_MAX_ATTEMPTS = 120


def _upload_and_wait_asset(client: TwelveLabs, video_path: str) -> str:
    with open(video_path, "rb") as f:
        asset = client.assets.create(method="direct", file=f)
    asset_id = asset.id
    if not asset_id:
        raise GeminiPipelineError("twelvelabs_failed", "Asset create returned no id")

    for _ in range(_ASSET_POLL_MAX_ATTEMPTS):
        current = client.assets.retrieve(asset_id)
        status = (current.status or "").strip().lower()
        if status == "ready":
            return asset_id
        if status == "failed":
            raise GeminiPipelineError(
                "twelvelabs_failed",
                "Twelve Labs asset processing failed",
            )
        time.sleep(_ASSET_POLL_INTERVAL_S)

    raise GeminiPipelineError(
        "twelvelabs_failed",
        "Twelve Labs asset did not become ready in time",
    )


def _analyze_stream_text(
    client: TwelveLabs,
    *,
    model_name: str,
    asset_id: str,
    input_text: str,
    max_tokens: int,
) -> str:
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
    raw = "".join(chunks).strip()
    if not raw:
        raise GeminiPipelineError("twelvelabs_empty", "Empty Pegasus stream output")
    return raw


def _run_main_analysis_sync(
    *,
    api_key: str,
    video_path: str,
    input_text: str,
    model_name: str,
    max_tokens: int,
) -> tuple[str, str]:
    client = TwelveLabs(api_key=api_key)
    asset_id = _upload_and_wait_asset(client, video_path)
    raw_text = _analyze_stream_text(
        client,
        model_name=model_name,
        asset_id=asset_id,
        input_text=input_text,
        max_tokens=max_tokens,
    )
    return raw_text, asset_id


async def analyze_clip_with_twelvelabs(
    video_path: str,
    metadata: ClipAnalysisMetadata,
    *,
    settings: Settings | None = None,
    job_id: str = "",
    account_tier: str | None = None,
) -> tuple[GeminiClipAnalysis, str]:
    """
    Pegasus main analysis — same output contract as ``analyze_clip_with_gemini``.

    Returns (parsed analysis, Twelve Labs asset_id) for enrichment reuse.
    """
    cfg = settings or get_settings()
    if not (cfg.twelvelabs_api_key or "").strip():
        raise GeminiPipelineError(
            "twelvelabs_not_configured",
            "Missing ONFLOW_TWELVELABS_API_KEY",
        )

    if not os.path.isfile(video_path) or os.path.getsize(video_path) == 0:
        raise GeminiPipelineError(
            "twelvelabs_invalid_response",
            "Video path invalid before Pegasus",
        )

    tier = account_tier or "pro"
    prompt_pack = build_pegasus_clip_analysis_prompt(metadata, tier)
    model = (cfg.twelvelabs_model or "pegasus1.5").strip()
    max_retries = max(0, cfg.twelvelabs_max_retries)
    timeout_s = cfg.twelvelabs_timeout_seconds
    max_tokens = max(256, cfg.twelvelabs_max_output_tokens)
    t0 = time.perf_counter()

    logger.info(
        "event=twelvelabs_analysis_started job_id=%s model=%s path_tail=%s",
        job_id or "-",
        model,
        os.path.basename(video_path),
    )

    last_exc: BaseException | None = None
    attempts = max_retries + 1
    tl_asset_id = ""

    for attempt in range(attempts):
        try:

            async def _call() -> tuple[str, str]:
                return await asyncio.to_thread(
                    _run_main_analysis_sync,
                    api_key=cfg.twelvelabs_api_key,
                    video_path=video_path,
                    input_text=prompt_pack.input_text,
                    model_name=model,
                    max_tokens=max_tokens,
                )

            raw_text, tl_asset_id = await asyncio.wait_for(_call(), timeout=timeout_s)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)

            logger.info(
                "event=twelvelabs_raw_response job_id=%s len=%d asset_id=%s head=%.300s",
                job_id or "-",
                len(raw_text),
                tl_asset_id[:12] if tl_asset_id else "-",
                raw_text[:300],
            )

            parse_retried = False
            while True:
                try:
                    data = parse_gemini_clip_analysis_dict(raw_text)
                    parsed = validate_gemini_clip_analysis(data)
                    break
                except GeminiPipelineError as pe:
                    if pe.reason in PARSE_RETRY_REASONS and not parse_retried:
                        parse_retried = True
                        logger.warning(
                            "event=twelvelabs_parse_retry job_id=%s reason=%s",
                            job_id or "-",
                            pe.reason,
                        )
                        raw_text, tl_asset_id = await asyncio.wait_for(_call(), timeout=timeout_s)
                        continue
                    raise

            parsed = apply_expected_mechanics_gate(parsed, metadata)
            try:
                validate_usefulness(
                    parsed,
                    first_pass_readiness=metadata.first_pass_readiness,
                )
            except UsefulnessRejected as e:
                logger.info(
                    "event=twelvelabs_usefulness_rejected job_id=%s provider=twelvelabs detail=%s",
                    job_id or "-",
                    str(e),
                )
                raise GeminiPipelineError("gemini_usefulness_rejected", str(e)) from e

            logger.info(
                "event=twelvelabs_analysis_succeeded job_id=%s model=%s elapsed_ms=%s asset_id=%s",
                job_id or "-",
                model,
                elapsed_ms,
                tl_asset_id[:12] if tl_asset_id else "-",
            )
            return parsed, tl_asset_id

        except GeminiPipelineError:
            raise
        except asyncio.TimeoutError:
            logger.info(
                "event=twelvelabs_analysis_failed job_id=%s reason=timeout",
                job_id or "-",
            )
            raise GeminiPipelineError("twelvelabs_failed", "Pegasus analysis timed out") from None
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "event=twelvelabs_analysis_attempt_failed job_id=%s attempt=%s error=%s",
                job_id or "-",
                attempt + 1,
                str(exc)[:200],
            )
            if attempt >= attempts - 1:
                break
            await asyncio.sleep(0.5 * (attempt + 1))

    detail = str(last_exc)[:200] if last_exc else "unknown"
    raise GeminiPipelineError("twelvelabs_failed", detail)
