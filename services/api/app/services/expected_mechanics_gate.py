"""
Gate and sanitize expected_mechanics — user-tagged trick context only, never trick detection.
"""
from __future__ import annotations

import re
from app.schemas.gemini_analysis import (
    GeminiClipAnalysis,
    GeminiExpectedMechanics,
    GeminiExpectedMechanicsCheckpoint,
)
from app.services.gemini_prompt import ClipAnalysisMetadata
from app.services.gemini_output_quality import VAGUE_CUE_PATTERNS, VAGUE_DRILL_PATTERNS
from app.services.trick_registry import resolve_trick

# Claims that imply automated trick ID — reject the whole block if any match.
_TRICK_DETECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bwe\s+detected\b", re.I),
    re.compile(r"\b(ai|the\s+model|the\s+system)\s+(detected|identified|recognized)\b", re.I),
    re.compile(r"\btrick\s+detection\b", re.I),
    re.compile(r"\brecognized\s+(your|the)\s+trick\b", re.I),
    re.compile(r"\bidentified\s+(your|the)\s+trick\b", re.I),
    re.compile(r"\b(classified|labeled)\s+(this|your)\s+(clip|attempt)\s+as\b", re.I),
)

_GENERIC_ONLY_LINES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*keep\s+practic", re.I),
    re.compile(r"^\s*focus\s+on\s+balance\b", re.I),
    re.compile(r"^\s*commit\s+more\b", re.I),
    re.compile(r"^\s*stay\s+balanced\b", re.I),
    re.compile(r"^\s*work\s+on\s+timing\b", re.I),
)


def _first_user_trick_label(meta: ClipAnalysisMetadata) -> str:
    raw = (meta.user_trick_label or "").strip()
    if not raw or raw.lower() == "none":
        return ""
    return raw.split(",")[0].strip()


def _concat_em_text(em: GeminiExpectedMechanics) -> str:
    parts: list[str] = [
        em.trick_name,
        em.overview,
        em.best_next_try,
        em.drill or "",
    ]
    for c in em.checkpoints:
        parts.extend([c.expected, c.observed, c.impact])
    return " ".join(parts)


def _forbidden_trick_detection(text: str) -> bool:
    return any(p.search(text) for p in _TRICK_DETECTION_PATTERNS)


def _line_too_generic(s: str) -> bool:
    t = s.strip()
    if len(t) < 12:
        return True
    for p in _GENERIC_ONLY_LINES:
        if p.search(t):
            return True
    for p in VAGUE_CUE_PATTERNS:
        if p.search(t):
            return True
    return False


def _drill_bad(s: str | None) -> bool:
    if not s or not s.strip():
        return False
    t = s.strip()
    if len(t) < 14:
        return True
    for p in VAGUE_DRILL_PATTERNS:
        if p.search(t):
            return True
    return False


def _checkpoint_row_ok(c: GeminiExpectedMechanicsCheckpoint) -> bool:
    if _line_too_generic(c.expected) or _line_too_generic(c.observed) or _line_too_generic(c.impact):
        return False
    return True


def apply_expected_mechanics_gate(
    analysis: GeminiClipAnalysis,
    metadata: ClipAnalysisMetadata,
) -> GeminiClipAnalysis:
    """
    Drop or keep expected_mechanics based on user tags, registry support, readiness, and wording.
    """
    em_in = analysis.expected_mechanics
    if em_in is None:
        return analysis

    try:
        em = GeminiExpectedMechanics.model_validate(em_in.model_dump())
    except Exception:
        return analysis.model_copy(update={"expected_mechanics": None})

    label = _first_user_trick_label(metadata)
    if not label:
        return analysis.model_copy(update={"expected_mechanics": None})

    entry = resolve_trick(label)
    if entry is None or not entry.checkpoints:
        return analysis.model_copy(update={"expected_mechanics": None})

    readiness = (metadata.first_pass_readiness or "usable").strip().lower()
    if readiness == "insufficient":
        return analysis.model_copy(update={"expected_mechanics": None})

    text_blob = _concat_em_text(em)
    if _forbidden_trick_detection(text_blob):
        return analysis.model_copy(update={"expected_mechanics": None})

    kept_rows = [c for c in em.checkpoints if _checkpoint_row_ok(c)]
    if len(kept_rows) < 2:
        return analysis.model_copy(update={"expected_mechanics": None})

    drill_out = em.drill.strip() if em.drill else None
    if _drill_bad(drill_out):
        drill_out = None

    overview = em.overview.strip()
    bnt = em.best_next_try.strip()
    if len(overview) < 40 or len(bnt) < 20:
        return analysis.model_copy(update={"expected_mechanics": None})

    out = GeminiExpectedMechanics(
        trick_name=entry.name,
        overview=overview[:900],
        checkpoints=kept_rows[:4],
        best_next_try=bnt[:420],
        drill=drill_out[:320] if drill_out else None,
    )
    if _forbidden_trick_detection(_concat_em_text(out)):
        return analysis.model_copy(update={"expected_mechanics": None})

    return analysis.model_copy(update={"expected_mechanics": out})
