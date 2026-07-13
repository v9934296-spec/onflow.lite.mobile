"""
Normalize and validate main Gemini clip analysis JSON (single place, defensive).

Failure codes are specific where possible; callers map to job failure_reason.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.schemas.gemini_analysis import GeminiClipAnalysis, GeminiExpectedMechanics
from app.services.gemini_pipeline_error import GeminiPipelineError

# Reasons that may justify one additional generate+parse attempt (see gemini_clip_analyzer).
PARSE_RETRY_REASONS = frozenset(
    {
        "gemini_empty",
        "gemini_malformed_json",
        "gemini_schema_mismatch",
    }
)


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences; tolerate ```json / ``` labels and trailing fences."""
    cleaned = text.strip()
    for _ in range(4):
        if not cleaned.startswith("```"):
            break
        first_nl = cleaned.find("\n")
        if first_nl == -1:
            cleaned = cleaned[3:].lstrip()
            continue
        body = cleaned[first_nl + 1 :]
        if body.rstrip().endswith("```"):
            body = body.rstrip()[:-3].rstrip()
        cleaned = body.strip()
    return cleaned


def _extract_json_object(text: str) -> str:
    """
    If the model prepends prose, take the first balanced {...} block.
    Rejects trailing prose after the closing brace (except whitespace and optional ```).
    """
    s = text.strip()
    start = s.find("{")
    if start < 0:
        raise GeminiPipelineError("gemini_malformed_json", "No JSON object found in model output")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                chunk = s[start : i + 1]
                tail = s[i + 1 :].strip()
                if tail:
                    tail_no_fence = tail.replace("`", "").strip()
                    if tail_no_fence:
                        raise GeminiPipelineError(
                            "gemini_malformed_json",
                            "Extra prose after JSON object",
                        )
                return chunk
    raise GeminiPipelineError("gemini_malformed_json", "Unbalanced JSON object in model output")


def parse_gemini_clip_analysis_dict(raw_text: str) -> dict[str, Any]:
    """
    Parse model output text to a dict (strict JSON path + balanced-object fallback).
    Raises GeminiPipelineError with gemini_empty | gemini_malformed_json.
    """
    if not (raw_text or "").strip():
        raise GeminiPipelineError("gemini_empty", "Empty model output")

    unfenced = _strip_json_fences(raw_text)

    if not unfenced.strip():
        raise GeminiPipelineError("gemini_empty", "Empty model output after stripping fences")

    try:
        data = json.loads(unfenced)
    except json.JSONDecodeError:
        try:
            extracted = _extract_json_object(unfenced)
            data = json.loads(extracted)
        except json.JSONDecodeError as e:
            raise GeminiPipelineError("gemini_malformed_json", f"Invalid JSON: {e!s}") from e

    if not isinstance(data, dict):
        raise GeminiPipelineError("gemini_malformed_json", "JSON root must be object")

    return data


def validate_gemini_clip_analysis(data: dict[str, Any]) -> GeminiClipAnalysis:
    """Pydantic validate; raises GeminiPipelineError(gemini_schema_mismatch, ...)."""
    d = dict(data)
    em_raw = d.pop("expected_mechanics", None)
    try:
        base = GeminiClipAnalysis.model_validate({**d, "expected_mechanics": None})
    except ValidationError as e:
        raise GeminiPipelineError(
            "gemini_schema_mismatch",
            str(e)[:400],
        ) from e
    if em_raw is None:
        return base
    try:
        em = GeminiExpectedMechanics.model_validate(em_raw)
        return base.model_copy(update={"expected_mechanics": em})
    except ValidationError:
        return base


def parse_and_validate_clip_analysis(raw_text: str) -> GeminiClipAnalysis:
    """Convenience: dict parse + schema validate."""
    d = parse_gemini_clip_analysis_dict(raw_text)
    return validate_gemini_clip_analysis(d)
