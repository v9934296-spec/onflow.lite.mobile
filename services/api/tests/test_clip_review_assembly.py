"""Tests for clip review result assembly — all code paths."""
from __future__ import annotations

from app.schemas.gemini_analysis import (
    GeminiClipAnalysis,
    GeminiExpectedMechanics,
    GeminiExpectedMechanicsCheckpoint,
)
from app.services.clip_review_assembly import assemble_clip_review_result, build_completed_result_from_gemini


def _first_pass(readiness: str = "usable") -> dict:
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
        "processing_notes": ["OnFlow does not classify tricks."],
        "review_summary_base": "Clip looks usable.",
    }


def test_assembly_without_gemini() -> None:
    result = assemble_clip_review_result(
        _first_pass(), "kickflip", None, gemini_attempted=False
    )
    assert "normalized_review" in result
    assert result["normalized_review"]["model"] == "gemini"
    assert result["clip_label"] == "kickflip"
    assert result["review_readiness"] == "usable"
    assert result["coaching"] is None
    assert result["landed"] == "unclear"
    assert "Gemini" not in " ".join(result["processing_notes"])


def test_assembly_gemini_attempted_but_failed() -> None:
    result = assemble_clip_review_result(
        _first_pass(), "ollie", None, gemini_attempted=True
    )
    assert result["coaching"] is None
    assert result["landed"] == "unclear"
    assert any("did not complete" in n for n in result["processing_notes"])


def test_assembly_includes_progression_fields() -> None:
    enrichment = {
        "review_addendum": "",
        "observation_bullets": [],
        "coaching": {
            "timing": "Pop slightly early",
            "foot_placement": None,
            "body_position": None,
            "board_control": None,
            "commitment": None,
            "balance": None,
            "style_notes": None,
            "improvement_drill": "Ten slow ollies",
        },
        "landed": "yes",
    }
    result = assemble_clip_review_result(
        _first_pass(), "kickflip", enrichment, gemini_attempted=True
    )
    assert result.get("primary_issue_key") == "timing"
    assert result.get("review_method") == "first_pass_plus_gemini"
    assert result.get("gemini_used") is True
    assert result.get("best_drill") == "Ten slow ollies"


def test_assembly_with_gemini_coaching() -> None:
    enrichment = {
        "review_addendum": "Approach looks solid.",
        "observation_bullets": ["Good speed"],
        "coaching": {
            "body_position": "Centered",
            "foot_placement": None,
            "timing": "Early pop",
            "board_control": None,
            "commitment": None,
            "balance": None,
            "style_notes": None,
            "improvement_drill": "Pop shuvit drill",
        },
        "landed": "yes",
    }
    result = assemble_clip_review_result(
        _first_pass(), "kickflip", enrichment, gemini_attempted=True
    )
    assert "Approach looks solid" in result["review_summary"]
    assert "Good speed" in result["observations"]
    assert result["coaching"]["body_position"] == "Centered"
    assert result["coaching"]["timing"] == "Early pop"
    assert "foot_placement" not in result["coaching"]
    assert result["landed"] == "yes"


def test_assembly_readiness_normalization() -> None:
    first = _first_pass()
    first["review_readiness"] = "bogus_value"
    result = assemble_clip_review_result(first, "ollie", None, gemini_attempted=False)
    assert result["review_readiness"] == "insufficient"


def test_assembly_empty_clip_label() -> None:
    result = assemble_clip_review_result(_first_pass(), "  ", None, gemini_attempted=False)
    assert result["clip_label"] == "untagged"


def _minimal_gemini() -> GeminiClipAnalysis:
    return GeminiClipAnalysis.model_validate(
        {
            "review_summary": "The clip shows a mostly committed attempt with the main weakness appearing at landing, where control looks unstable and weight placement seems slightly off-center. Timing through the movement looks decent, but the finish is less controlled than the setup.",
            "strengths": [
                "Commitment through the attempt is visible without a major hesitation.",
            ],
            "improvement_areas": [
                "Landing control looks unstable, with balance shifting on contact.",
            ],
            "actionable_cues": [
                {
                    "cue": "Stay more centered over the board on landing.",
                    "why_it_matters": "A more centered finish can reduce the side-to-side instability visible on contact.",
                    "drill": "Practice short rolling land-and-hold reps focusing only on balanced contact.",
                }
            ],
            "observations": [
                {
                    "title": "Landing balance shift",
                    "detail": "Balance appears to drift slightly off-center right as the board reconnects with the ground.",
                    "severity": "warning",
                }
            ],
            "quality_signals": [],
            "uncertainty_notes": ["Board visibility is limited through part of the clip."],
            "processing_notes": [],
        }
    )


def test_build_completed_includes_expected_mechanics_when_present() -> None:
    em = GeminiExpectedMechanics(
        trick_name="Kickflip",
        overview="Because you tagged this as a kickflip: " + "x" * 40,
        checkpoints=[
            GeminiExpectedMechanicsCheckpoint(
                expected="Front foot slides up the deck then flicks off the nose pocket.",
                observed="In your clip the flick angle looks shallow before the board starts to flip.",
                impact="That likely caused under-rotation and a late catch window.",
            ),
            GeminiExpectedMechanicsCheckpoint(
                expected="Back foot pops straight down through the ball of the foot for height.",
                observed="The tail motion is visible; pop timing looks slightly ahead of the flick.",
                impact="The timing gap can flatten the flip arc.",
            ),
        ],
        best_next_try="Prioritize a slightly later flick after the tail leaves the ground.",
        drill="Ten slow stationary kickflip attempts filming the feet from the side.",
    )
    gem = _minimal_gemini().model_copy(update={"expected_mechanics": em})
    first = _first_pass()
    out = build_completed_result_from_gemini(gem, first, "kickflip", trick="kickflip")
    assert "expected_mechanics" in out
    assert out["expected_mechanics"]["trick_name"] == "Kickflip"
    assert len(out["expected_mechanics"]["checkpoints"]) == 2


def test_build_completed_omits_expected_mechanics_when_absent() -> None:
    gem = _minimal_gemini()
    first = _first_pass()
    out = build_completed_result_from_gemini(gem, first, "kickflip", trick="kickflip")
    assert "expected_mechanics" not in out


def test_build_completed_land_score_only_when_landed_yes() -> None:
    gem = _minimal_gemini().model_copy(update={"land_score": 8.0})
    first = _first_pass()

    out_yes = build_completed_result_from_gemini(
        gem,
        first,
        "kickflip",
        gemini_enrichment={"review_addendum": "", "landed": "yes"},
        trick="kickflip",
    )
    assert out_yes["landed"] == "yes"
    assert out_yes["land_score"] == 8.0

    out_no = build_completed_result_from_gemini(
        gem,
        first,
        "kickflip",
        gemini_enrichment={"review_addendum": "", "landed": "no"},
        trick="kickflip",
    )
    assert out_no["landed"] == "no"
    assert out_no["land_score"] is None
