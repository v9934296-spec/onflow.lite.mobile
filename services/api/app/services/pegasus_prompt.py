"""
Pegasus-specific prompts for Twelve Labs video analysis.

PROMPT_VERSION tracks semantic changes for regression (parallel to Gemini PROMPT_VERSION).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.services.gemini_prompt import ClipAnalysisMetadata, get_response_schema_hint
from app.services.gemini_reviewer import SYSTEM_PROMPT as GEMINI_ENRICHMENT_SYSTEM
from app.services.gemini_structured_schemas import ENRICHMENT_RESPONSE_JSON_SCHEMA
from app.services.gemini_tier_prompt import build_tier_aware_prompt

PEGASUS_PROMPT_VERSION = "pegasus-v1"


@dataclass(frozen=True)
class PegasusPromptPack:
    """Combined input for Twelve Labs AnalyzePromptV2 (single input_text)."""

    input_text: str
    prompt_version: str = PEGASUS_PROMPT_VERSION


_PEGASUS_SYSTEM = """\
You are an expert skateboarding clip analyst using native video understanding.

Analyze the clip temporally: setup → pop/trick motion → peak → landing → rollaway/end.
Focus on what is visible in the footage — body mechanics, board relationship, timing, balance.

Rules (strict — same product contract as OnFlow Gemini reviews):
- You are NOT a trick detector. Never invent trick names unless the skater's tags name them.
- No confidence scores, no grades, no hype or therapy language.
- Honest roll-away gate: if the clip ends before a clear rollaway, do not claim a clean landing.
- Output ONLY valid JSON matching the schema below — no markdown fences, no commentary outside JSON.
- If a field is not observable, use null or empty arrays as appropriate; do not fabricate.

JSON schema (exact keys required):
"""


def build_pegasus_clip_analysis_prompt(
    metadata: ClipAnalysisMetadata,
    tier: str,
) -> PegasusPromptPack:
    """Tier-aware Pegasus main analysis prompt (Pro checkpoints when applicable)."""
    pack = build_tier_aware_prompt(metadata, tier)
    schema = get_response_schema_hint()
    input_text = (
        f"{_PEGASUS_SYSTEM}\n{schema}\n\n"
        f"--- SYSTEM INSTRUCTIONS ---\n{pack.system_prompt}\n\n"
        f"--- USER CONTEXT ---\n{pack.user_prompt}\n\n"
        "Respond with JSON only."
    ).strip()
    return PegasusPromptPack(input_text=input_text)


def _enrichment_user_context(clip_label: str, clip_metadata: dict[str, Any] | None) -> str:
    meta = clip_metadata or {}
    stance = meta.get("stance", "")
    obstacle = meta.get("obstacle", "")
    tricks_raw = meta.get("tricks", [])
    tricks = tricks_raw if isinstance(tricks_raw, list) else []

    lines: list[str] = [
        "Skater context (may be empty) — use only as self-reported tags, not detections:",
    ]
    if stance:
        lines.append(f"- stance: {stance}")
    if obstacle:
        lines.append(f"- terrain/obstacle: {obstacle}")
    if tricks:
        trick_strs = [t.strip() for t in tricks if isinstance(t, str) and t.strip()][:5]
        if trick_strs:
            lines.append(f"- tricks named by skater: {', '.join(trick_strs)}")
    if clip_label and clip_label.strip() and clip_label.strip() != "untagged":
        lines.append(f'- clip label: "{clip_label.strip()}"')

    lines.append(
        "Watch the attached clip and produce JSON as specified. "
        "Pay close attention to the end of the clip to determine if the trick was landed."
    )
    return "\n".join(lines)


def build_pegasus_enrichment_prompt(
    clip_label: str,
    clip_metadata: dict[str, Any] | None = None,
) -> PegasusPromptPack:
    """Pegasus enrichment pass — coaching + landed signal."""
    schema_json = json.dumps(ENRICHMENT_RESPONSE_JSON_SCHEMA, indent=2)
    user_ctx = _enrichment_user_context(clip_label, clip_metadata)
    input_text = (
        f"{GEMINI_ENRICHMENT_SYSTEM}\n\n"
        f"Required JSON schema:\n{schema_json}\n\n"
        f"{user_ctx}\n\n"
        "Respond with JSON only — no markdown fences."
    ).strip()
    return PegasusPromptPack(input_text=input_text)
