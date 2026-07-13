"""normalize_review: aliases, coercion, honest weak output."""
from __future__ import annotations

import json

from app.schemas.gemini_analysis import GeminiClipAnalysis
from app.services.review_normalize import normalize_review


def test_normalize_from_gemini_model() -> None:
    raw = {
        "review_summary": "x" * 25,
        "strengths": ["Visible commitment line one here ok."],
        "improvement_areas": ["Landing control issue visible on contact here ok."],
        "actionable_cues": [
            {
                "cue": "Stay centered",
                "why_it_matters": "Balance control reduces drift visible on contact.",
                "drill": "Static landings 5x",
            }
        ],
        "observations": [
            {
                "title": "Landing",
                "detail": "Weight shifts on the board at contact with visible foot pressure.",
                "severity": "warning",
            }
        ],
        "quality_signals": [
            {"name": "timing", "score": 6.0, "assessment": "ok", "evidence": None},
            {"name": "landing_control", "score": 8.0, "assessment": "ok", "evidence": None},
        ],
        "uncertainty_notes": ["Angle limits detail.", "Clip is short."],
        "processing_notes": [],
    }
    g = GeminiClipAnalysis.model_validate(raw)
    out = normalize_review(g, "kickflip", "regular")
    assert out["model"] == "gemini"
    assert "regular" in (out["label"] or "").lower() or "kickflip" in (out["label"] or "").lower()
    assert out["drill"] == "Static landings 5x"
    assert out["score"] == 7  # avg of 6 and 8
    assert len(out["what_you_did_right"]) >= 1
    assert len(out["what_to_fix"]) >= 1


def test_alias_keys_dict() -> None:
    d = {
        "summary": "Short summary line here for test.",
        "what_you_did_right": ["Did well one", "Did well two"],
        "what_to_fix": ["Fix one"],
        "quality_signals": [],
    }
    out = normalize_review(d, "", "")
    assert out["summary"].startswith("Short summary")
    assert len(out["what_you_did_right"]) == 2


def test_json_string_input() -> None:
    payload = {
        "review_summary": "Summary text here for testing min length.",
        "strengths": ["Strength line one ok here."],
        "improvement_areas": ["Fix line one ok here."],
        "actionable_cues": [
            {"cue": "c", "why_it_matters": "d" * 30, "drill": None},
        ],
        "observations": [
            {
                "title": "L",
                "detail": "Weight shifts on the board at contact with visible foot pressure.",
                "severity": "warning",
            }
        ],
        "quality_signals": [],
        "uncertainty_notes": ["u1", "u2"],
        "processing_notes": [],
    }
    raw = "```json\n" + json.dumps(payload) + "\n```"
    out = normalize_review(raw, "", "")
    assert len(out["summary"]) >= 10


def test_weak_structure_honest_message() -> None:
    out = normalize_review({}, "", "")
    assert out["model"] == "gemini"
    assert "thin" in out["summary"].lower() or "extracted" in out["summary"].lower()
    assert out["what_you_did_right"] == []
    assert out["what_to_fix"] == []


def test_coerces_explicit_score_from_string() -> None:
    """Backend / mobile may emit score as string; normalize stays stable."""
    d = {
        "review_summary": "Summary line here long enough ok.",
        "score": "7.4",
        "strengths": ["Visible line one ok here."],
        "improvement_areas": ["Fix line one ok here."],
        "actionable_cues": [],
        "observations": [],
        "quality_signals": [],
        "uncertainty_notes": [],
        "processing_notes": [],
    }
    out = normalize_review(d, "", "")
    assert out["score"] == 7


def test_normalize_non_object_input_does_not_raise() -> None:
    """Loose API payloads must degrade to honest empty structure, not crash."""
    out = normalize_review([1, 2, 3], "", "")
    assert out["model"] == "gemini"
    assert isinstance(out["summary"], str)
    assert out["what_you_did_right"] == []
    assert out["what_to_fix"] == []


def test_enrichment_drill_fallback() -> None:
    d = {
        "review_summary": "x" * 25,
        "strengths": ["S1"],
        "improvement_areas": ["I1"],
        "actionable_cues": [{"cue": "c", "why_it_matters": "w" * 30, "drill": None}],
        "observations": [
            {
                "title": "L",
                "detail": "Weight shifts on the board at contact with visible foot pressure.",
                "severity": "warning",
            }
        ],
        "quality_signals": [],
        "uncertainty_notes": ["a", "b"],
        "processing_notes": [],
    }
    g = GeminiClipAnalysis.model_validate(d)
    enr = {"coaching": {"improvement_drill": "Ollie practice line"}}
    out = normalize_review(g, "", "", enrichment=enr)
    assert out["drill"] == "Ollie practice line"
