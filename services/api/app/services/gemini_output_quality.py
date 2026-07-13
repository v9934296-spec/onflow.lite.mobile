"""
Usefulness gate: reject generic filler even when JSON schema validates.
"""
from __future__ import annotations

import re
from typing import Literal

from app.schemas.gemini_analysis import GeminiClipAnalysis

ReadinessTier = Literal["usable", "limited", "insufficient"]

# Phrases that suggest empty reassurance (not exhaustive; paired with structural checks)
# Vague coaching cues — reject even if length looks OK
VAGUE_CUE_PATTERNS = [
    re.compile(r"\bwork\s+on\s+timing\b", re.I),
    re.compile(r"\bstay\s+balanced\b", re.I),
    re.compile(r"\bcommit\s+more\b", re.I),
    re.compile(r"\bbe\s+more\s+confident\b", re.I),
    re.compile(r"\bpractice\s+more\b", re.I),
    re.compile(r"\bfocus\s+on\s+timing\b", re.I),
    re.compile(r"\bkeep\s+practicing\b", re.I),
    re.compile(r"\btry\s+to\s+stay\s+centered\b", re.I),
    re.compile(r"\bgive\s+it\s+time\b", re.I),
    re.compile(r"\bjust\s+send\s+it\b", re.I),
]

VAGUE_DRILL_PATTERNS = [
    re.compile(r"\bkeep\s+practic", re.I),
    re.compile(r"\bpractice\s+more\b", re.I),
    re.compile(r"\bjust\s+keep\s+trying\b", re.I),
    re.compile(r"\bstay\s+consistent\b", re.I),
    re.compile(r"\bwork\s+on\s+it\s+more\b", re.I),
]

GENERIC_PATTERNS = [
    re.compile(r"\bkeep\s+practic", re.I),
    re.compile(r"\bgreat\s+effort", re.I),
    re.compile(r"\bnice\s+attempt", re.I),
    re.compile(r"\bstay\s+confident", re.I),
    re.compile(r"\bcontinue\s+working\s+on\s+consistency", re.I),
    re.compile(r"\bgood\s+job\s+overall", re.I),
    re.compile(r"\bgood\s+job\s+trying", re.I),
    re.compile(r"\bfocus\s+on\s+confidence", re.I),
    re.compile(r"\bgreat\s+work\s*!", re.I),
    re.compile(r"\bjust\s+keep\s+at\s+it", re.I),
    re.compile(r"\bawesome\s+job", re.I),
    re.compile(r"\bmaking\s+great\s+progress", re.I),
    re.compile(r"\breally\s+solid\s+effort", re.I),
    re.compile(r"\byou(?:'|’)ve\s+got\s+this", re.I),
    re.compile(r"\bkeep\s+pushing", re.I),
    re.compile(r"\bamazing\s+work", re.I),
    re.compile(r"\bso\s+proud", re.I),
    re.compile(r"\bcrush(?:ing|ed)\s+it", re.I),
]


class UsefulnessRejected(Exception):
    """Raised when analysis is too generic to accept as completed."""


def _mostly_generic_text(text: str) -> bool:
    t = text.strip().lower()
    if len(t) < 40:
        return True
    hits = sum(1 for p in GENERIC_PATTERNS if p.search(t))
    return hits >= 2


def _word_jaccard(a: str, b: str) -> float:
    wa = {w for w in re.findall(r"[a-z0-9']+", a.lower()) if len(w) > 2}
    wb = {w for w in re.findall(r"[a-z0-9']+", b.lower()) if len(w) > 2}
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union else 0.0


def _has_concrete_strength(a: GeminiClipAnalysis) -> bool:
    for s in a.strengths:
        if len(s.strip()) >= 28 and not _mostly_generic_text(s):
            return True
    return False


def _has_concrete_improvement(a: GeminiClipAnalysis) -> bool:
    for s in a.improvement_areas:
        if _improvement_area_specific_enough(s):
            return True
    return False


def _drill_specific_enough(drill: str | None) -> bool:
    if not drill or not drill.strip():
        return True
    t = drill.strip()
    if len(t) < 14:
        return False
    for p in VAGUE_DRILL_PATTERNS:
        if p.search(t):
            return False
    if _mostly_generic_text(t):
        return False
    return bool(
        re.search(
            r"\b(foot|feet|heel|toe|shoulder|hip|knee|board|deck|pop|flick|ollie|stance|"
            r"stationary|static|slow|repeat|reps|hold|compress|slide|roll|rolling|land|landing)\b",
            t,
            re.I,
        )
    )


def _cue_specific_enough(cue: str, why: str, drill: str | None) -> bool:
    combined = f"{cue} {why} {drill or ''}".strip()
    if len(combined) < 58:
        return False
    for p in VAGUE_CUE_PATTERNS:
        if p.search(combined):
            return False
    if drill and not _drill_specific_enough(drill):
        return False
    # Visible mechanics anchor
    if not re.search(
        r"\b(foot|feet|heel|toe|shoulder|hip|knee|chest|weight|board|deck|truck|bolt|pop|"
        r"flick|catch|land|compress|angle|frame|motion|timing|air|rotation|ollie|nose|tail)\b",
        combined,
        re.I,
    ):
        return False
    # Prefer consequence / relation language; long combined text can pass without it
    if len(combined) < 76 and not re.search(
        r"\b(which|because|so\s+that|pulls|drifts|cuts|forces|keeps|leaves|lands|opens|closes|"
        r"before|after|during|while)\b",
        combined,
        re.I,
    ):
        return False
    return True


def _improvement_area_specific_enough(s: str) -> bool:
    t = s.strip()
    if len(t) < 38:
        return False
    if _mostly_generic_text(t):
        return False
    for p in VAGUE_CUE_PATTERNS:
        if p.search(t):
            return False
    return bool(
        re.search(
            r"\b(foot|feet|shoulder|hip|board|deck|land|pop|timing|balance|weight|angle|frame)\b",
            t,
            re.I,
        )
    )


def _has_actionable_cue(a: GeminiClipAnalysis) -> bool:
    for c in a.actionable_cues:
        cue = c.cue.strip()
        why = c.why_it_matters.strip()
        drill = c.drill.strip() if c.drill else None
        if len(cue) >= 14 and len(why) >= 28:
            if _mostly_generic_text(cue + " " + why):
                continue
            if not _cue_specific_enough(cue, why, drill):
                continue
            return True
    return False


def _has_evidence_observation(a: GeminiClipAnalysis) -> bool:
    for o in a.observations:
        combined = f"{o.title} {o.detail}"
        if len(combined.strip()) >= 44:
            if re.search(
                r"\b(foot|feet|knee|shoulder|hip|weight|timing|pop|land|compress|roll|board|stance|balance|motion|angle|frame|deck|truck|push)\b",
                combined,
                re.I,
            ):
                return True
    return False


def _repetitive_parallel_lists(a: GeminiClipAnalysis) -> bool:
    """Reject copy-paste between strengths and improvements."""
    for s in a.strengths:
        for i in a.improvement_areas:
            if _word_jaccard(s, i) >= 0.55 and min(len(s), len(i)) >= 20:
                return True
    return False


def _improvement_areas_repeat_vague_idea(a: GeminiClipAnalysis) -> bool:
    """Reject two improvement lines that paraphrase the same vague coaching."""
    areas = [x.strip() for x in a.improvement_areas if x.strip()]
    for i in range(len(areas)):
        for j in range(i + 1, len(areas)):
            if _word_jaccard(areas[i], areas[j]) >= 0.62:
                return True
            if any(p.search(areas[i]) for p in VAGUE_CUE_PATTERNS) and any(
                p.search(areas[j]) for p in VAGUE_CUE_PATTERNS
            ):
                return True
    return False


def _uncertainty_adequate_for_limited(a: GeminiClipAnalysis) -> bool:
    notes = [u.strip() for u in a.uncertainty_notes if u and u.strip()]
    if len(notes) < 2:
        return False
    good = sum(1 for u in notes if len(u) >= 22)
    return good >= 2


def validate_usefulness(
    a: GeminiClipAnalysis,
    *,
    first_pass_readiness: ReadinessTier | str = "usable",
) -> None:
    """
    Fail closed if output is fluffy or missing concrete mechanics content.
    When the automated video pass is already "limited", require substantive uncertainty_notes.
    """
    tier = str(first_pass_readiness).strip().lower()
    if tier not in ("usable", "limited", "insufficient"):
        tier = "usable"

    if _mostly_generic_text(a.review_summary):
        raise UsefulnessRejected("review_summary too generic or short")

    if not _has_concrete_strength(a):
        raise UsefulnessRejected("no concrete visible strength")

    if not _has_concrete_improvement(a):
        raise UsefulnessRejected("no concrete improvement area")

    if _improvement_areas_repeat_vague_idea(a):
        raise UsefulnessRejected("improvement areas repeat the same vague idea")

    if not _has_actionable_cue(a):
        raise UsefulnessRejected("no actionable cue tied to mechanics")

    if not _has_evidence_observation(a):
        raise UsefulnessRejected("observations lack visible/mechanical evidence")

    if _repetitive_parallel_lists(a):
        raise UsefulnessRejected("strengths and improvements overlap too much (repetitive)")

    if tier == "limited" and not _uncertainty_adequate_for_limited(a):
        raise UsefulnessRejected(
            "limited clip quality requires at least two substantive uncertainty_notes naming specific limits"
        )
