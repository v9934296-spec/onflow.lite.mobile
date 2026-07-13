"""Unit tests for Gemini clip analysis JSON normalization (no live API)."""

import json

import pytest

from app.services.gemini_analysis_parse import (
    parse_gemini_clip_analysis_dict,
    validate_gemini_clip_analysis,
)
from app.services.gemini_pipeline_error import GeminiPipelineError


def test_fenced_json_parses() -> None:
    inner = json.dumps(
        {
            "review_summary": "x" * 25,
            "strengths": ["Concrete visible strength line one here."],
            "improvement_areas": ["Concrete visible issue line one here ok."],
            "actionable_cues": [
                {
                    "cue": "Stay centered on landing practice",
                    "why_it_matters": "Balance control reduces drift visible on contact with pavement.",
                    "drill": "Hold static landings.",
                }
            ],
            "observations": [
                {
                    "title": "Landing",
                    "detail": "Weight shifts on the board at contact with visible foot pressure change.",
                    "severity": "warning",
                }
            ],
            "quality_signals": [],
            "uncertainty_notes": ["Angle limits detail."],
            "processing_notes": [],
        }
    )
    raw = "```json\n" + inner + "\n```"
    d = parse_gemini_clip_analysis_dict(raw)
    assert len(d["review_summary"]) == 25


def test_empty_raises_gemini_empty() -> None:
    with pytest.raises(GeminiPipelineError) as ei:
        parse_gemini_clip_analysis_dict("")
    assert ei.value.reason == "gemini_empty"


def test_malformed_json_raises() -> None:
    with pytest.raises(GeminiPipelineError) as ei:
        parse_gemini_clip_analysis_dict("not json {")
    assert ei.value.reason == "gemini_malformed_json"


def test_schema_mismatch_raises() -> None:
    with pytest.raises(GeminiPipelineError) as ei:
        validate_gemini_clip_analysis({"review_summary": "short"})
    assert ei.value.reason == "gemini_schema_mismatch"


def test_land_score_bounds_and_rounding() -> None:
    parsed = validate_gemini_clip_analysis(
        {
            "review_summary": "x" * 25,
            "strengths": ["Concrete visible strength line one here."],
            "improvement_areas": ["Concrete visible issue line one here ok."],
            "actionable_cues": [
                {
                    "cue": "Stay centered on landing practice",
                    "why_it_matters": "Balance control reduces drift visible on contact with pavement.",
                    "drill": "Hold static landings.",
                }
            ],
            "observations": [
                {
                    "title": "Landing",
                    "detail": "Weight shifts on the board at contact with visible foot pressure change.",
                    "severity": "warning",
                }
            ],
            "quality_signals": [],
            "land_score": 7.37,
            "uncertainty_notes": ["Angle limits detail."],
            "processing_notes": [],
        }
    )
    assert parsed.land_score == 7.4


def test_land_score_rejects_out_of_range() -> None:
    with pytest.raises(GeminiPipelineError) as ei:
        validate_gemini_clip_analysis(
            {
                "review_summary": "x" * 25,
                "strengths": ["Concrete visible strength line one here."],
                "improvement_areas": ["Concrete visible issue line one here ok."],
                "actionable_cues": [
                    {
                        "cue": "Stay centered on landing practice",
                        "why_it_matters": "Balance control reduces drift visible on contact with pavement.",
                        "drill": "Hold static landings.",
                    }
                ],
                "observations": [
                    {
                        "title": "Landing",
                        "detail": "Weight shifts on the board at contact with visible foot pressure change.",
                        "severity": "warning",
                    }
                ],
                "quality_signals": [],
                "land_score": 11.0,
                "uncertainty_notes": ["Angle limits detail."],
                "processing_notes": [],
            }
        )
    assert ei.value.reason == "gemini_schema_mismatch"
