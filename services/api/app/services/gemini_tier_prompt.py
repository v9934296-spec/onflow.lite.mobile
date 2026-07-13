"""
Tier-aware prompt enhancement for Gemini clip analysis.

Free tier: standard prompt (gemini_prompt.py — unchanged).
Pro tier: same prompt + trick-specific biomechanical checkpoints
injected into the user prompt when the trick is in the registry.

This does NOT replace gemini_prompt.py — it wraps it.
"""
from __future__ import annotations

from app.services.gemini_prompt import (
    ClipAnalysisMetadata,
    GeminiPromptPack,
    build_gemini_clip_analysis_prompt,
)
from app.services.trick_registry import format_checkpoints_for_prompt, resolve_trick


def build_tier_aware_prompt(
    metadata: ClipAnalysisMetadata,
    tier: str,
) -> GeminiPromptPack:
    """
    Build the Gemini prompt pack, enhanced for Pro tier.

    Free tier → standard prompt, no changes.
    Pro tier → standard prompt + biomechanical checkpoint block
    appended to the user prompt when the trick has defined checkpoints.
    """
    base = build_gemini_clip_analysis_prompt(metadata)

    if tier != "pro":
        return base

    # Extract trick name from metadata
    trick_label = metadata.user_trick_label.strip()
    if not trick_label or trick_label == "none":
        return base

    # Try to resolve the trick — handles aliases too
    # If user entered multiple tricks, use the first one
    first_trick = trick_label.split(",")[0].strip()
    entry = resolve_trick(first_trick)

    if not entry or not entry.checkpoints:
        return base

    checkpoint_block = format_checkpoints_for_prompt(first_trick)

    enhanced_user_prompt = f"""{base.user_prompt}

--- PRO TIER: TRICK-SPECIFIC ANALYSIS ---
The skater tagged this clip as: {entry.name}

{checkpoint_block}

For each checkpoint you CAN observe in the clip, include a specific observation
noting what you see — reference the body part and mechanic by name. If a checkpoint
is not visible due to angle, framing, or clip length, skip it and note the limit
in uncertainty_notes. Do NOT fabricate observations for checkpoints you cannot see.

Score the quality_signals with these checkpoints in mind — a clean kickflip flick
matters more to the landing_control and board_control signals than generic "looks stable."
"""

    return GeminiPromptPack(
        system_prompt=base.system_prompt,
        user_prompt=enhanced_user_prompt.strip(),
        response_schema_hint=base.response_schema_hint,
    )
