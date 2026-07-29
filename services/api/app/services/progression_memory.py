"""
Deterministic progression metadata from Gemini analysis + enrichment (no trick detection).
"""
from __future__ import annotations

import re
from typing import Any

from app.schemas.gemini_analysis import GeminiClipAnalysis

# (coaching_field, issue_key, human_label)
_COACHING_PRIORITY: list[tuple[str, str, str]] = [
    ("timing", "timing", "Timing"),
    ("foot_placement", "front_foot_control", "Front foot control"),
    ("body_position", "body_alignment", "Body alignment"),
    ("board_control", "board_control", "Board control"),
    ("balance", "balance", "Balance"),
    ("commitment", "commitment", "Commitment"),
]

_CUE_INFER_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\btiming\b", re.I), "timing", "Timing"),
    (re.compile(r"\bfront\s*foot|flick|bolt", re.I), "front_foot_control", "Front foot control"),
    (re.compile(r"\bshoulder|hips|posture|alignment|upper\s*body", re.I), "body_alignment", "Body alignment"),
    (re.compile(r"\bboard|deck|flip|catch", re.I), "board_control", "Board control"),
    (re.compile(r"\bbalance|weight|center", re.I), "balance", "Balance"),
    (re.compile(r"\bcommit", re.I), "commitment", "Commitment"),
]


def _first_actionable_cue_text(gemini: GeminiClipAnalysis) -> str | None:
    for c in gemini.actionable_cues:
        t = (c.cue or "").strip()
        if len(t) >= 8:
            return t
    return None


def _first_coaching_sentence(coaching: dict[str, str] | None) -> str | None:
    if not coaching:
        return None
    for _k, v in coaching.items():
        if isinstance(v, str) and len(v.strip()) >= 12:
            return v.strip()
    return None


def derive_best_cue_drill(
    gemini: GeminiClipAnalysis | None,
    coaching: dict[str, str] | None,
) -> tuple[str | None, str | None]:
    best_cue: str | None = None
    if gemini is not None:
        best_cue = _first_actionable_cue_text(gemini)
    if not best_cue:
        best_cue = _first_coaching_sentence(coaching)

    best_drill: str | None = None
    if coaching:
        d = coaching.get("improvement_drill")
        if isinstance(d, str) and d.strip():
            best_drill = d.strip()
    if not best_drill and gemini is not None and gemini.actionable_cues:
        for c in gemini.actionable_cues:
            if c.drill and str(c.drill).strip():
                best_drill = str(c.drill).strip()
                break
    return best_cue, best_drill


def derive_primary_issue(
    coaching: dict[str, str] | None,
    landed: str | None,
    gemini: GeminiClipAnalysis | None,
) -> tuple[str | None, str | None]:
    if coaching:
        for field, key, label in _COACHING_PRIORITY:
            val = coaching.get(field)
            if isinstance(val, str) and val.strip():
                return key, label

    if landed == "no" and gemini.actionable_cues:
        combined = " ".join(
            f"{c.cue} {c.why_it_matters}" for c in gemini.actionable_cues[:3]
        )
        for pat, key, label in _CUE_INFER_PATTERNS:
            if pat.search(combined):
                return key, label
    return None, None


def build_technical_limit_summary(
    readiness: str,
    uncertainty_notes: list[str],
    processing_notes: list[str],
) -> str:
    parts: list[str] = [f"Review readiness: {readiness}."]
    for u in uncertainty_notes[:3]:
        u = (u or "").strip()
        if u:
            parts.append(u)
    # One processing note that signals limits (not the fixed disclaimer line)
    for p in processing_notes:
        pl = (p or "").strip()
        if not pl or "Canonical analysis uses" in pl:
            continue
        if any(
            x in pl.lower()
            for x in ("limited", "unclear", "short", "angle", "visibility", "supplementary")
        ):
            parts.append(pl[:180])
            break
    out = " ".join(parts)
    return out[:400] if len(out) > 400 else out


def enrichment_succeeded(enrichment: dict[str, Any] | None) -> bool:
    if not enrichment:
        return False
    add = enrichment.get("review_addendum")
    if isinstance(add, str) and add.strip():
        return True
    bullets = enrichment.get("observation_bullets")
    if isinstance(bullets, list) and any(isinstance(b, str) and b.strip() for b in bullets):
        return True
    raw = enrichment.get("coaching")
    if isinstance(raw, dict):
        for v in raw.values():
            if isinstance(v, str) and v.strip():
                return True
    return False


def compute_progression_fields(
    gemini: GeminiClipAnalysis | None,
    first_pass: dict[str, Any],
    gemini_enrichment: dict[str, Any] | None,
    *,
    uncertainty_notes: list[str],
    processing_notes: list[str],
) -> dict[str, Any]:
    readiness = first_pass.get("review_readiness")
    if readiness not in ("usable", "limited", "insufficient"):
        readiness = "limited"

    raw_coaching = gemini_enrichment.get("coaching") if gemini_enrichment else None
    coaching: dict[str, str] | None = None
    if isinstance(raw_coaching, dict):
        coaching = {
            k: str(v).strip()
            for k, v in raw_coaching.items()
            if isinstance(v, str) and v.strip()
        }
        if not coaching:
            coaching = None

    landed: str | None = None
    if gemini_enrichment:
        lv = gemini_enrichment.get("landed", "unclear")
        if lv in ("yes", "no", "unclear"):
            landed = lv

    gemini_used = enrichment_succeeded(gemini_enrichment)
    review_method = "first_pass_plus_gemini" if gemini_used else "first_pass_only"

    technical_limit_summary = build_technical_limit_summary(
        str(readiness), uncertainty_notes, processing_notes
    )

    best_cue, best_drill = derive_best_cue_drill(gemini, coaching)
    primary_issue_key, primary_issue_label = derive_primary_issue(coaching, landed, gemini)

    return {
        "primary_issue_key": primary_issue_key,
        "primary_issue_label": primary_issue_label,
        "best_cue": best_cue,
        "best_drill": best_drill,
        "review_method": review_method,
        "gemini_used": gemini_used,
        "technical_limit_summary": technical_limit_summary,
    }
