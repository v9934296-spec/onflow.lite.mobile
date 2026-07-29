"""
Canonical Gemini clip analysis: required for any completed job.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from google import genai
from google.genai import types

from app.core.config import Settings, get_settings
from app.core.tiers import resolve_gemini_model_for_tier
from app.schemas.gemini_analysis import GeminiClipAnalysis
from app.services.expected_mechanics_gate import apply_expected_mechanics_gate
from app.services.gemini_analysis_parse import (
    PARSE_RETRY_REASONS,
    parse_gemini_clip_analysis_dict,
    validate_gemini_clip_analysis,
)
from app.services.gemini_output_quality import UsefulnessRejected, validate_usefulness
from app.services.gemini_pipeline_error import GeminiPipelineError
from app.services.gemini_prompt import (
    ClipAnalysisMetadata,
    GeminiPromptPack,
    build_gemini_clip_analysis_prompt,
)

logger = logging.getLogger(__name__)

# JSON Schema for `GenerateContentConfig.response_schema` (API-enforced shape).
# Older google-genai builds only allow `response_schema`; newer ones also accept `response_json_schema`.
_GEMINI_CLIP_RESPONSE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "review_summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvement_areas": {"type": "array", "items": {"type": "string"}},
        "actionable_cues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cue": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "drill": {"type": "string"},
                },
                "required": ["cue", "why_it_matters"],
            },
        },
        "observations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "good", "warning"]},
                },
                "required": ["title", "detail"],
            },
        },
        "quality_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": [
                            "balance",
                            "stability",
                            "timing",
                            "landing_control",
                            "body_alignment",
                            "pop_explosion",
                            "board_control",
                        ],
                    },
                    "score": {"type": "number"},
                    "assessment": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "assessment"],
            },
        },
        "land_score": {"type": "number", "minimum": 0, "maximum": 10},
        "uncertainty_notes": {"type": "array", "items": {"type": "string"}},
        "processing_notes": {"type": "array", "items": {"type": "string"}},
        "expected_mechanics": {
            "type": "object",
            "properties": {
                "trick_name": {"type": "string"},
                "overview": {"type": "string"},
                "checkpoints": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "properties": {
                            "expected": {"type": "string"},
                            "observed": {"type": "string"},
                            "impact": {"type": "string"},
                        },
                        "required": ["expected", "observed", "impact"],
                    },
                },
                "best_next_try": {"type": "string"},
                "drill": {"type": "string"},
            },
            "required": ["trick_name", "overview", "checkpoints", "best_next_try"],
        },
    },
    "required": [
        "review_summary",
        "strengths",
        "improvement_areas",
        "actionable_cues",
        "observations",
    ],
}

# Re-export for callers that imported from this module
__all__ = ["GeminiPipelineError", "analyze_clip_with_gemini", "guess_clip_mime"]


def _guess_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".m4v": "video/x-m4v",
        ".avi": "video/x-msvideo",
    }.get(ext, "video/mp4")


def _read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, OSError)):
        return True
    msg = str(exc).lower()
    if "503" in msg or "502" in msg or "504" in msg or "429" in msg:
        return True
    if "unavailable" in msg or "temporar" in msg or "timeout" in msg:
        return True
    if "connection" in msg or "reset" in msg:
        return True
    return False


async def _wait_file_active(client: genai.Client, name: str) -> types.File:
    for _ in range(120):
        f = await client.aio.files.get(name=name)
        st = f.state
        if st == types.FileState.ACTIVE:
            return f
        if st == types.FileState.FAILED:
            raise GeminiPipelineError("gemini_unavailable", "Uploaded file processing failed on provider.")
        await asyncio.sleep(1)
    raise GeminiPipelineError("gemini_timeout", "Provider did not activate uploaded file in time.")


def _extract_text_from_response(
    response: types.GenerateContentResponse,
    *,
    job_id: str,
    model: str,
) -> str:
    """Read concatenated text; classify empty/blocked/safety (no secrets)."""
    has_cand = bool(response.candidates)
    n_cand = len(response.candidates or [])
    pf = response.prompt_feedback
    pf_block = getattr(pf, "block_reason", None) if pf else None
    finish = None
    if response.candidates and response.candidates[0] is not None:
        finish = getattr(response.candidates[0], "finish_reason", None)

    logger.info(
        "event=gemini_response_meta job_id=%s model=%s has_candidates=%s n_candidates=%s "
        "prompt_block=%s finish_reason=%s",
        job_id or "-",
        model,
        has_cand,
        n_cand,
        pf_block,
        finish,
    )

    if pf and pf_block and pf_block != types.BlockedReason.BLOCKED_REASON_UNSPECIFIED:
        msg = (pf.block_reason_message or str(pf_block))[:300]
        raise GeminiPipelineError("gemini_blocked", f"Prompt blocked: {msg}")

    if not response.candidates:
        raise GeminiPipelineError(
            "gemini_blocked",
            "No candidates in response",
        )

    c0 = response.candidates[0]
    fr = getattr(c0, "finish_reason", None)
    fr_str = str(fr) if fr is not None else ""

    raw = (response.text or "").strip()
    preview = raw[:240].replace("\n", " ") if raw else ""
    logger.info(
        "event=gemini_response_text job_id=%s model=%s text_len=%s finish_reason=%s preview=%s",
        job_id or "-",
        model,
        len(raw),
        fr_str,
        preview,
    )

    if raw:
        return raw

    if fr is not None:
        if fr in (
            types.FinishReason.SAFETY,
            types.FinishReason.PROHIBITED_CONTENT,
            types.FinishReason.BLOCKLIST,
            types.FinishReason.IMAGE_SAFETY,
            types.FinishReason.IMAGE_PROHIBITED_CONTENT,
            types.FinishReason.RECITATION,
        ):
            raise GeminiPipelineError("gemini_blocked", f"finish_reason={fr_str}")
        if fr == types.FinishReason.MAX_TOKENS:
            raise GeminiPipelineError(
                "gemini_malformed_json",
                "Empty output with MAX_TOKENS (likely truncated JSON)",
            )
    raise GeminiPipelineError("gemini_empty", "Empty model text after generation")


async def _generate_once(
    *,
    client: genai.Client,
    model: str,
    file_path: str,
    pack: GeminiPromptPack,
    temperature: float,
    max_output_tokens: int,
    job_id: str,
) -> str:
    file_size = os.path.getsize(file_path)
    mime_type = _guess_mime(file_path)
    inline_max = get_settings().gemini_inline_max_bytes

    if file_size <= inline_max:
        video_bytes = _read_file(file_path)
        video_part = types.Part(
            inline_data=types.Blob(data=video_bytes, mime_type=mime_type),
        )
    else:
        uploaded = await client.aio.files.upload(
            file=file_path,
            config=types.UploadFileConfig(mime_type=mime_type),
        )
        ready = await _wait_file_active(client, uploaded.name)
        video_part = types.Part(
            file_data=types.FileData(file_uri=ready.uri, mime_type=ready.mime_type or mime_type),
        )

    response = await client.aio.models.generate_content(
        model=model,
        contents=types.Content(
            parts=[video_part, types.Part.from_text(text=pack.user_prompt)],
        ),
        config=types.GenerateContentConfig(
            system_instruction=pack.system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
            response_schema=_GEMINI_CLIP_RESPONSE_JSON_SCHEMA,
        ),
    )
    return _extract_text_from_response(response, job_id=job_id, model=model)


def guess_clip_mime(path: str) -> str:
    return _guess_mime(path)


async def analyze_clip_with_gemini(
    video_path: str,
    metadata: ClipAnalysisMetadata,
    *,
    settings: Settings | None = None,
    job_id: str = "",
    prompt_pack_override: GeminiPromptPack | None = None,
    account_tier: str | None = None,
) -> GeminiClipAnalysis:
    """
    Full path: canonical prompt pack → provider call → JSON parse → Pydantic validate → usefulness gate.

    Pass ``account_tier`` so the model id comes from ``resolve_gemini_model_for_tier`` (production).
    When omitted, ``settings.gemini_model_resolved`` is used for backward compatibility only.
    """
    cfg = settings or get_settings()
    if not (cfg.gemini_api_key or "").strip():
        raise GeminiPipelineError("gemini_not_configured", "Missing GEMINI / ONFLOW API key")

    if not os.path.isfile(video_path) or os.path.getsize(video_path) == 0:
        raise GeminiPipelineError("gemini_invalid_response", "Video path invalid before Gemini")

    pack = prompt_pack_override or build_gemini_clip_analysis_prompt(metadata)
    if account_tier is not None:
        model = resolve_gemini_model_for_tier(account_tier, cfg)
    else:
        model = cfg.gemini_model_resolved
    max_retries = max(0, cfg.gemini_max_retries)
    timeout_s = cfg.gemini_timeout_seconds
    t0 = time.perf_counter()

    logger.info(
        "event=gemini_analysis_started job_id=%s model=%s path_tail=%s",
        job_id or "-",
        model,
        os.path.basename(video_path),
    )

    client = genai.Client(api_key=cfg.gemini_api_key)
    last_exc: BaseException | None = None
    attempts = max_retries + 1

    for attempt in range(attempts):
        try:
            async def _call() -> str:
                return await _generate_once(
                    client=client,
                    model=model,
                    file_path=video_path,
                    pack=pack,
                    temperature=cfg.gemini_temperature,
                    max_output_tokens=cfg.gemini_max_output_tokens,
                    job_id=job_id,
                )

            raw_text = await asyncio.wait_for(_call(), timeout=timeout_s)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)

            parse_retried = False
            while True:
                try:
                    logger.info(
                        "event=gemini_raw_response job_id=%s len=%d head=%.300s",
                        job_id or "-",
                        len(raw_text),
                        raw_text[:300],
                    )
                    data = parse_gemini_clip_analysis_dict(raw_text)
                    try:
                        parsed = validate_gemini_clip_analysis(data)
                    except GeminiPipelineError as v_err:
                        if v_err.reason == "gemini_schema_mismatch":
                            logger.error(
                                "event=gemini_schema_validation_failed job_id=%s error=%s keys=%s",
                                job_id or "-",
                                (v_err.detail or "")[:500],
                                list(data.keys()) if isinstance(data, dict) else "not_a_dict",
                            )
                        raise
                    break
                except GeminiPipelineError as pe:
                    if pe.reason in PARSE_RETRY_REASONS and not parse_retried:
                        parse_retried = True
                        logger.warning(
                            "event=gemini_parse_retry job_id=%s model=%s reason=%s detail=%s",
                            job_id or "-",
                            model,
                            pe.reason,
                            (pe.detail or "")[:180],
                        )
                        raw_text = await asyncio.wait_for(_call(), timeout=timeout_s)
                        continue
                    logger.warning(
                        "event=gemini_parse_failed job_id=%s model=%s reason=%s detail=%s",
                        job_id or "-",
                        model,
                        pe.reason,
                        (pe.detail or "")[:220],
                    )
                    raise

            parsed = apply_expected_mechanics_gate(parsed, metadata)
            try:
                validate_usefulness(
                    parsed,
                    first_pass_readiness=metadata.first_pass_readiness,
                )
            except UsefulnessRejected as e:
                logger.info(
                    "event=gemini_usefulness_rejected job_id=%s detail=%s",
                    job_id or "-",
                    str(e),
                )
                raise GeminiPipelineError("gemini_usefulness_rejected", str(e)) from e

            logger.info(
                "event=gemini_analysis_succeeded job_id=%s model=%s elapsed_ms=%s parse_retry=%s",
                job_id or "-",
                model,
                elapsed_ms,
                parse_retried,
            )
            return parsed

        except GeminiPipelineError:
            raise
        except asyncio.TimeoutError:
            logger.info("event=gemini_analysis_failed job_id=%s reason=timeout", job_id or "-")
            raise GeminiPipelineError("gemini_timeout", f"Exceeded {timeout_s}s") from None
        except Exception as e:
            last_exc = e
            if attempt + 1 < attempts and _is_transient_error(e):
                logger.info(
                    "event=gemini_analysis_retry job_id=%s attempt=%s/%s err=%s",
                    job_id or "-",
                    attempt + 1,
                    attempts,
                    str(e)[:120],
                )
                await asyncio.sleep(0.8 * (attempt + 1))
                continue
            if _is_transient_error(e):
                raise GeminiPipelineError("gemini_unavailable", str(e)[:200]) from e
            logger.exception("event=gemini_analysis_failed job_id=%s unexpected", job_id or "-")
            raise GeminiPipelineError("gemini_invalid_response", str(e)[:200]) from e

    raise GeminiPipelineError("gemini_unavailable", str(last_exc)[:200] if last_exc else "unknown")


def _parse_model_json(raw_text: str) -> dict[str, Any]:
    """Deprecated alias for tests; use parse_gemini_clip_analysis_dict."""
    return parse_gemini_clip_analysis_dict(raw_text)
