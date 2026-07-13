"""
Stable mobile-facing review block from Gemini-shaped output — no fabricated coaching.

Accepts validated GeminiClipAnalysis, loose dicts (alias keys), or JSON-ish strings.
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.schemas.gemini_analysis import GeminiClipAnalysis

_MAX_BULLET = 12
_MAX_SUMMARY = 1200


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _parse_jsonish(raw: str) -> dict[str, Any]:
    s = _strip_json_fences(raw)
    if not s:
        return {}
    try:
        data = json.loads(s)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        # first balanced object
        start = s.find("{")
        if start < 0:
            return {}
        depth = 0
        for i in range(start, len(s)):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(s[start : i + 1])
                        return data if isinstance(data, dict) else {}
                    except json.JSONDecodeError:
                        return {}
        return {}


def _coerce_to_dict(raw_ai_response: Any) -> dict[str, Any]:
    if raw_ai_response is None:
        return {}
    if isinstance(raw_ai_response, GeminiClipAnalysis):
        return raw_ai_response.model_dump()
    if isinstance(raw_ai_response, dict):
        return dict(raw_ai_response)
    if hasattr(raw_ai_response, "model_dump"):
        dumped = raw_ai_response.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(raw_ai_response, str):
        return _parse_jsonish(raw_ai_response)
    return {}


def _clean_str(v: Any, max_len: int = 2000) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if len(s) > max_len:
        s = s[: max_len - 1] + "…"
    return s


def _str_list(val: Any, *, max_items: int = _MAX_BULLET) -> list[str]:
    if val is None:
        return []
    out: list[str] = []
    if isinstance(val, str):
        for line in re.split(r"[\n\r]+", val):
            t = line.strip().lstrip("•-*").strip()
            if len(t) >= 3:
                out.append(t)
    elif isinstance(val, list):
        for x in val:
            t = _clean_str(x, max_len=800)
            if len(t) >= 3:
                out.append(t)
    return out[:max_items]


def _coerce_score_0_10(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        x = float(val)
    except (TypeError, ValueError):
        return None
    if x != x:  # nan
        return None
    r = int(round(x))
    if r < 0:
        return 0
    if r > 10:
        return 10
    return r


def _aggregate_scores_from_quality_signals(signals: Any) -> int | None:
    if not isinstance(signals, list) or not signals:
        return None
    nums: list[float] = []
    for s in signals:
        if not isinstance(s, dict):
            continue
        sc = s.get("score")
        if sc is None and "Score" in s:
            sc = s["Score"]
        if isinstance(sc, (int, float)):
            nums.append(float(sc))
    if not nums:
        return None
    return _coerce_score_0_10(sum(nums) / len(nums))


def _pick_summary(d: dict[str, Any]) -> str:
    for key in ("review_summary", "summary", "reviewSummary", "overview"):
        t = _clean_str(d.get(key), max_len=_MAX_SUMMARY)
        if len(t) >= 8:
            return t
    return ""


def _pick_strengths(d: dict[str, Any]) -> list[str]:
    for key in (
        "strengths",
        "what_you_did_right",
        "positives",
        "did_well",
        "wins",
    ):
        if key in d and d[key] is not None:
            return _str_list(d[key])
    return []


def _pick_fixes(d: dict[str, Any]) -> list[str]:
    for key in (
        "improvement_areas",
        "what_to_fix",
        "weaknesses",
        "fixes",
        "issues",
        "improvements",
    ):
        if key in d and d[key] is not None:
            return _str_list(d[key])
    return []


def _pick_drill(d: dict[str, Any], enrichment: dict[str, Any] | None) -> str | None:
    cues = d.get("actionable_cues")
    if isinstance(cues, list):
        for c in cues:
            if not isinstance(c, dict):
                continue
            dr = c.get("drill") or c.get("Drill")
            t = _clean_str(dr, max_len=500)
            if t:
                return t
    coaching = d.get("coaching")
    if isinstance(coaching, dict):
        t = _clean_str(coaching.get("improvement_drill"), max_len=500)
        if t:
            return t
    if enrichment and isinstance(enrichment.get("coaching"), dict):
        t = _clean_str(enrichment["coaching"].get("improvement_drill"), max_len=500)
        if t:
            return t
    return None


def _build_label(trick: str, stance: str) -> str | None:
    parts: list[str] = []
    st = stance.strip()
    tr = trick.strip()
    if st:
        parts.append(st.replace("_", " ").title())
    if tr:
        parts.append(tr)
    if not parts:
        return None
    return " · ".join(parts)


def normalize_review(
    raw_ai_response: Any,
    trick: str = "",
    stance: str = "",
    *,
    enrichment: dict[str, Any] | None = None,
    model: str = "gemini",
) -> dict[str, Any]:
    """
    Produce a stable dict for mobile:
    summary, score, label, what_you_did_right, what_to_fix, drill, model.

    Does not invent bullets: empty lists when nothing usable. Score is optional
    aggregate from quality_signals or explicit score fields; None if unknown.
    """
    d = _coerce_to_dict(raw_ai_response)
    # Alias top-level score
    explicit_score = d.get("score")
    if explicit_score is None and "overall_score" in d:
        explicit_score = d.get("overall_score")

    summary = _pick_summary(d)
    right = _pick_strengths(d)
    fix = _pick_fixes(d)
    score = _coerce_score_0_10(explicit_score)
    if score is None:
        score = _aggregate_scores_from_quality_signals(d.get("quality_signals"))

    drill = _pick_drill(d, enrichment)
    label = _build_label(trick, stance)

    weak = (
        len(summary) < 12
        and not right
        and not fix
    )
    if weak:
        summary = (
            "Review structure from the model was too thin to break into bullets here. "
            "Use the full readout (summary, observations, readiness) for this clip."
        )
        if not right and not fix:
            pass  # keep empty lists — honest

    # Trim summary if we had content but it's borderline empty after cleaning
    if not summary.strip():
        summary = (
            "No usable summary line was extracted; see observations and technical notes."
        )

    model_norm = (model or "gemini").strip().lower()
    if model_norm not in ("gemini", "pegasus"):
        model_norm = "gemini"

    return {
        "summary": summary.strip()[:_MAX_SUMMARY],
        "score": score,
        "label": label,
        "what_you_did_right": right,
        "what_to_fix": fix,
        "drill": drill,
        "model": model_norm,
    }
