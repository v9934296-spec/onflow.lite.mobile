"""
Prompt pack, JSON parsing, schema + usefulness gates for Gemini clip analysis.
"""
from __future__ import annotations

import json

import pytest

from app.schemas.gemini_analysis import GeminiClipAnalysis
from app.services.gemini_clip_analyzer import GeminiPipelineError, _parse_model_json
from app.services.gemini_output_quality import UsefulnessRejected, validate_usefulness
from app.services.gemini_analysis_parse import validate_gemini_clip_analysis
from app.services.gemini_prompt import (
    ClipAnalysisMetadata,
    build_gemini_clip_analysis_prompt,
    get_response_schema_hint,
)


def test_prompt_builder_includes_critical_instructions() -> None:
    meta = ClipAnalysisMetadata.from_job_upload(
        video_path="/tmp/clip.mp4",
        clip_label="session-a",
        stance="regular",
        obstacle="flat",
        tricks=["kickflip"],
        duration_seconds=3.5,
        mime_type="video/mp4",
        first_pass_readiness="limited",
        technical_quality_summary="readiness=limited; low motion across sampled frames",
    )
    pack = build_gemini_clip_analysis_prompt(meta)
    low = pack.system_prompt.lower()
    assert "trick detection" in low
    assert "return json only" in low or "json only" in low
    assert "great effort" in low
    assert "grounded" in pack.user_prompt.lower()
    assert "filename:" in pack.user_prompt
    assert "first_pass_readiness" in pack.user_prompt
    assert "limited" in pack.user_prompt


def test_prompt_builder_safe_defaults_when_missing_fields() -> None:
    meta = ClipAnalysisMetadata.all_unknown()
    pack = build_gemini_clip_analysis_prompt(meta)
    assert "filename: unknown" in pack.user_prompt
    assert "duration_seconds: unknown" in pack.user_prompt
    assert "mime_type: unknown" in pack.user_prompt
    assert "user_trick_label: none" in pack.user_prompt
    assert "stance_label: none" in pack.user_prompt
    assert "notes: none" in pack.user_prompt
    assert "first_pass_readiness: usable" in pack.user_prompt


def test_prompt_includes_exact_schema_block() -> None:
    meta = ClipAnalysisMetadata.from_job_upload(
        video_path="/a/b.mp4",
        clip_label="t",
        stance="",
        obstacle="",
        tricks=[],
        duration_seconds=None,
        mime_type="video/mp4",
    )
    pack = build_gemini_clip_analysis_prompt(meta)
    block = get_response_schema_hint()
    assert block in pack.user_prompt
    assert "actionable_cues" in block
    assert "expected_mechanics" in block


def test_parse_accepts_json_inside_markdown_fences() -> None:
    """Fenced JSON is stripped and parsed; valid object is accepted."""
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
    d = _parse_model_json(raw)
    assert d["review_summary"] == "x" * 25


def test_parse_rejects_prose_after_json() -> None:
    raw = '{"a": 1} trailing prose'
    with pytest.raises(GeminiPipelineError) as ei:
        _parse_model_json(raw)
    assert ei.value.reason == "gemini_malformed_json"


def test_parse_rejects_non_json_content() -> None:
    with pytest.raises(GeminiPipelineError):
        _parse_model_json("```json\nhello\n```")


def test_parse_accepts_prose_before_json() -> None:
    payload = {
        "review_summary": "Summary text here for testing min length.",
        "strengths": ["Visible commitment line long enough here."],
        "improvement_areas": ["Landing control issue visible on contact here."],
        "actionable_cues": [
            {
                "cue": "Practice balanced landings on flat ground",
                "why_it_matters": "Centered weight reduces side drift visible at contact.",
                "drill": None,
            }
        ],
        "observations": [
            {
                "title": "Balance",
                "detail": "Foot placement on the board shifts during landing with visible motion.",
                "severity": "info",
            }
        ],
        "quality_signals": [],
        "uncertainty_notes": ["Clip angle limits board visibility."],
        "processing_notes": [],
    }
    raw = "Here is the output:\n" + json.dumps(payload)
    d = _parse_model_json(raw)
    assert d["review_summary"] == payload["review_summary"]


SAMPLE_GOOD = {
    "review_summary": "The clip shows a mostly committed attempt with the main weakness appearing at landing, where control looks unstable and weight placement seems slightly off-center. Timing through the movement looks decent, but the finish is less controlled than the setup.",
    "strengths": [
        "Commitment through the attempt is visible without a major hesitation.",
        "Timing into the movement looks relatively consistent from setup into takeoff.",
    ],
    "improvement_areas": [
        "Landing control looks unstable, with balance shifting on contact.",
        "Body alignment appears to open up a bit early, which may be affecting control through the finish.",
    ],
    "actionable_cues": [
        {
            "cue": "Stay more centered over the board on landing.",
            "why_it_matters": "A more centered finish can reduce the side-to-side instability visible on contact.",
            "drill": "Practice short rolling land-and-hold reps focusing only on balanced contact.",
        },
        {
            "cue": "Keep the shoulders quieter through the motion.",
            "why_it_matters": "Less upper-body opening can help timing and control stay more consistent through the finish.",
            "drill": "Try a few slower reps with attention on shoulder alignment.",
        },
    ],
    "observations": [
        {
            "title": "Landing balance shift",
            "detail": "Balance appears to drift slightly off-center right as the board reconnects with the ground.",
            "severity": "warning",
        },
        {
            "title": "Committed entry",
            "detail": "There is no obvious bailout before the main movement, which suggests solid commitment into the attempt.",
            "severity": "good",
        },
    ],
    "quality_signals": [
        {
            "name": "landing_control",
            "score": 5.8,
            "assessment": "Landing looks somewhat unstable and is the clearest weak point in the clip.",
            "evidence": "Weight appears to shift off-center on contact.",
        },
        {
            "name": "timing",
            "score": 6.4,
            "assessment": "Timing looks reasonably consistent, though the finish is less controlled than the entry.",
            "evidence": "The motion into the attempt is relatively smooth before the unstable landing.",
        },
        {
            "name": "board_control",
            "score": None,
            "assessment": "Board control is hard to judge confidently from this angle.",
            "evidence": "The deck is not fully visible through the whole motion.",
        },
    ],
    "uncertainty_notes": [
        "Board visibility is limited through part of the clip.",
        "The angle makes mid-motion detail harder to judge than the entry and landing.",
    ],
    "processing_notes": [],
}


def test_sample_good_passes_schema_and_usefulness() -> None:
    g = GeminiClipAnalysis.model_validate(SAMPLE_GOOD)
    validate_usefulness(g)


def test_tagged_registry_trick_prompt_includes_expected_mechanics_instructions() -> None:
    meta = ClipAnalysisMetadata.from_job_upload(
        video_path="/a/b.mp4",
        clip_label="t",
        stance="regular",
        obstacle="flat",
        tricks=["kickflip"],
        duration_seconds=3.0,
        mime_type="video/mp4",
    )
    pack = build_gemini_clip_analysis_prompt(meta)
    assert "USER-TAGGED TRICK CONTEXT" in pack.user_prompt
    assert "Kickflip" in pack.user_prompt
    assert "expected_mechanics" in pack.user_prompt


def test_malformed_expected_mechanics_dropped_at_validate() -> None:
    bad = {**SAMPLE_GOOD, "expected_mechanics": {"invalid": True}}
    g = validate_gemini_clip_analysis(bad)
    assert g.expected_mechanics is None


BAD_FILLER = {
    "review_summary": "Great effort overall and you are making progress.",
    "strengths": ["Good job trying."],
    "improvement_areas": ["Keep practicing."],
    "actionable_cues": [
        {
            "cue": "Stay confident.",
            "why_it_matters": "Confidence is important.",
            "drill": None,
        }
    ],
    "observations": [
        {
            "title": "Nice try",
            "detail": "This was a nice try and you should keep going.",
            "severity": "good",
        }
    ],
    "quality_signals": [],
    "uncertainty_notes": [],
    "processing_notes": [],
}


def test_vague_actionable_cue_rejected() -> None:
    vague = {
        **SAMPLE_GOOD,
        "actionable_cues": [
            {
                "cue": "Work on timing",
                "why_it_matters": "Timing matters for landing control.",
                "drill": None,
            }
        ],
    }
    g = GeminiClipAnalysis.model_validate(vague)
    with pytest.raises(UsefulnessRejected):
        validate_usefulness(g)


def test_sample_bad_fails_usefulness() -> None:
    g = GeminiClipAnalysis.model_validate(BAD_FILLER)
    with pytest.raises(UsefulnessRejected):
        validate_usefulness(g)


def test_limited_clip_requires_two_uncertainty_notes() -> None:
    g = GeminiClipAnalysis.model_validate(
        {**SAMPLE_GOOD, "uncertainty_notes": ["Only one substantive uncertainty note here ok."]},
    )
    with pytest.raises(UsefulnessRejected):
        validate_usefulness(g, first_pass_readiness="limited")


def test_duplicate_improvement_areas_rejected() -> None:
    line = (
        "Landing control looks unstable, with balance shifting on contact with the pavement "
        "during the attempt."
    )
    g = GeminiClipAnalysis.model_validate({**SAMPLE_GOOD, "improvement_areas": [line, line]})
    with pytest.raises(UsefulnessRejected):
        validate_usefulness(g)


def test_repetitive_strength_and_improvement_rejected() -> None:
    line = (
        "Landing shows visible weight drift on the board at contact with the ground surface "
        "during the attempt."
    )
    g = GeminiClipAnalysis.model_validate(
        {**SAMPLE_GOOD, "strengths": [line], "improvement_areas": [line]},
    )
    with pytest.raises(UsefulnessRejected):
        validate_usefulness(g)


def test_quality_signal_score_rounded_to_one_decimal() -> None:
    raw = {**SAMPLE_GOOD, "quality_signals": [{**SAMPLE_GOOD["quality_signals"][0], "score": 8.73}]}
    g = GeminiClipAnalysis.model_validate(raw)
    assert g.quality_signals[0].score == 8.7
