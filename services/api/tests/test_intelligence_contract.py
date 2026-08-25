"""Characterization tests for the current shared intelligence contract.

Freezes parse → validate → assemble behavior as production does it today.
No SDK calls. No production changes. Ugly behavior is intentional to lock.
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.schemas.clips import ClipResultPayload
from app.schemas.gemini_analysis import GeminiClipAnalysis
from app.services.clip_review_assembly import build_completed_result_from_gemini
from app.services.expected_mechanics_gate import apply_expected_mechanics_gate
from app.services.gemini_analysis_parse import (
    parse_gemini_clip_analysis_dict,
    validate_gemini_clip_analysis,
)
from app.services.gemini_pipeline_error import GeminiPipelineError
from app.services.gemini_prompt import ClipAnalysisMetadata
from tests.test_gemini_prompt_pack import SAMPLE_GOOD

_FIRST_CUE = SAMPLE_GOOD["actionable_cues"][0]["cue"]
_FIRST_OBS = SAMPLE_GOOD["observations"][0]


def _first_pass(*, readiness: str = "usable") -> dict:
    return {
        "video_readable": True,
        "duration_seconds": 3.0,
        "fps": 30.0,
        "frame_count_estimated": 90,
        "frames_sampled": 12,
        "motion_detected": True,
        "mean_brightness_0_1": 0.4,
        "review_readiness": readiness,
        "observations": ["Video opened.", "Duration ~3s."],
    }


def _analysis() -> GeminiClipAnalysis:
    parsed = validate_gemini_clip_analysis(dict(SAMPLE_GOOD))
    return apply_expected_mechanics_gate(parsed, ClipAnalysisMetadata.all_unknown())


def _assemble(
    analysis: GeminiClipAnalysis,
    *,
    review_model: str = "gemini",
    first_pass: dict | None = None,
    land_score: float | None = None,
    enrichment: dict | None = None,
) -> dict:
    gem = analysis if land_score is None else analysis.model_copy(update={"land_score": land_score})
    return build_completed_result_from_gemini(
        gem,
        first_pass if first_pass is not None else _first_pass(),
        "kickflip",
        gemini_enrichment=enrichment,
        trick="kickflip",
        review_model=review_model,
    )


def _payload(**kwargs) -> ClipResultPayload:
    return ClipResultPayload.model_validate(_assemble(_analysis(), **kwargs))


# --- 1. Valid provider JSON → GeminiClipAnalysis ---


def test_valid_json_parses_to_gemini_clip_analysis() -> None:
    data = parse_gemini_clip_analysis_dict(json.dumps(SAMPLE_GOOD))
    analysis = validate_gemini_clip_analysis(data)
    assert isinstance(analysis, GeminiClipAnalysis)
    assert analysis.review_summary == SAMPLE_GOOD["review_summary"]
    assert len(analysis.observations) == 2
    assert analysis.actionable_cues[0].cue == _FIRST_CUE


def test_fenced_valid_json_parses_to_gemini_clip_analysis() -> None:
    raw = "```json\n" + json.dumps(SAMPLE_GOOD) + "\n```"
    data = parse_gemini_clip_analysis_dict(raw)
    analysis = validate_gemini_clip_analysis(data)
    assert isinstance(analysis, GeminiClipAnalysis)
    assert analysis.review_summary == SAMPLE_GOOD["review_summary"]


# --- 2. Failure reasons as the parser actually emits them ---


def test_whitespace_only_is_gemini_empty() -> None:
    with pytest.raises(GeminiPipelineError) as ei:
        parse_gemini_clip_analysis_dict("   ")
    assert ei.value.reason == "gemini_empty"


def test_unclosed_object_is_gemini_malformed_json() -> None:
    with pytest.raises(GeminiPipelineError) as ei:
        parse_gemini_clip_analysis_dict('{"review_summary": ')
    assert ei.value.reason == "gemini_malformed_json"


def test_valid_json_invalid_schema_is_gemini_schema_mismatch() -> None:
    data = parse_gemini_clip_analysis_dict('{"review_summary": "hello"}')
    with pytest.raises(GeminiPipelineError) as ei:
        validate_gemini_clip_analysis(data)
    assert ei.value.reason == "gemini_schema_mismatch"


def test_leading_prose_then_valid_object_parses() -> None:
    """Observed: json.loads fails; balanced-object fallback keeps the first {...}."""
    raw = "Here is some extra explanation.\n" + json.dumps(SAMPLE_GOOD)
    data = parse_gemini_clip_analysis_dict(raw)
    assert data["review_summary"] == SAMPLE_GOOD["review_summary"]
    analysis = validate_gemini_clip_analysis(data)
    assert isinstance(analysis, GeminiClipAnalysis)


def test_trailing_prose_after_valid_object_is_gemini_malformed_json() -> None:
    """Observed: fallback extracts the object, then rejects a non-empty tail."""
    raw = json.dumps(SAMPLE_GOOD) + "\n\nHere is some extra explanation."
    with pytest.raises(GeminiPipelineError) as ei:
        parse_gemini_clip_analysis_dict(raw)
    assert ei.value.reason == "gemini_malformed_json"


# --- 3–4. Shared ClipResultPayload; provider labels ---


def test_gemini_assembly_validates_as_clip_result_payload() -> None:
    payload = _payload(review_model="gemini")
    assert payload.analysis_type == "skate_clip_review"
    assert payload.schema_version == 1


def test_twelve_labs_json_uses_the_same_gemini_clip_analysis_contract() -> None:
    """Twelve Labs already parses into GeminiClipAnalysis via the same functions."""
    data = parse_gemini_clip_analysis_dict(json.dumps(SAMPLE_GOOD))
    analysis = validate_gemini_clip_analysis(data)
    assert isinstance(analysis, GeminiClipAnalysis)
    payload = ClipResultPayload.model_validate(_assemble(analysis, review_model="gemini"))
    assert payload.analysis_type == "skate_clip_review"
    assert payload.schema_version == 1


def test_pegasus_review_model_currently_fails_normalized_review_literal() -> None:
    """Observed: NormalizedReviewPayload.model is Literal['gemini'] only.

    build_completed_result_from_gemini(..., review_model='pegasus') raises
    before returning. Freeze that. Do not widen the schema here.
    """
    with pytest.raises(ValidationError) as ei:
        _assemble(_analysis(), review_model="pegasus")
    assert ei.value.errors()[0]["loc"] == ("model",)
    assert ei.value.errors()[0]["input"] == "pegasus"


def test_gemini_normalized_review_model_label() -> None:
    payload = _payload(review_model="gemini")
    assert payload.normalized_review is not None
    assert payload.normalized_review.model == "gemini"


# --- 5. landed / land_score ---


def test_land_score_survives_when_landed_yes() -> None:
    payload = _payload(
        land_score=8.0,
        enrichment={"review_addendum": "", "landed": "yes"},
    )
    assert payload.landed == "yes"
    assert payload.land_score == 8.0


def test_land_score_dropped_when_landed_no() -> None:
    payload = _payload(
        land_score=8.0,
        enrichment={"review_addendum": "", "landed": "no"},
    )
    assert payload.landed == "no"
    assert payload.land_score is None


# --- 6. observations ---


def test_observations_survive_as_flattened_presentation_text() -> None:
    payload = _payload()
    assert "[Video pass] Video opened." in payload.observations
    assert "[Video pass] Duration ~3s." in payload.observations
    expected = f"{_FIRST_OBS['title']}: {_FIRST_OBS['detail']} [{_FIRST_OBS['severity']}]"
    assert expected in payload.observations


# --- 7. review_readiness ---


@pytest.mark.parametrize("readiness", ["usable", "limited", "insufficient"])
def test_known_review_readiness_survives_assembly(readiness: str) -> None:
    payload = _payload(first_pass=_first_pass(readiness=readiness))
    assert payload.review_readiness == readiness


def test_unknown_review_readiness_becomes_limited() -> None:
    payload = _payload(first_pass=_first_pass(readiness="bogus_value"))
    assert payload.review_readiness == "limited"


# --- 8. best / actionable cue ---


def test_best_and_actionable_cue_survive_assembly() -> None:
    payload = _payload()
    assert payload.best_cue == _FIRST_CUE
    assert payload.first_actionable_cue_shown == _FIRST_CUE
