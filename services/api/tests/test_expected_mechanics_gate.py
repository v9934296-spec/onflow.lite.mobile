"""expected_mechanics gating — user-tagged registry tricks only; no trick-detection copy."""
from __future__ import annotations

from app.schemas.gemini_analysis import (
    GeminiClipAnalysis,
    GeminiExpectedMechanics,
    GeminiExpectedMechanicsCheckpoint,
)
from app.services.expected_mechanics_gate import apply_expected_mechanics_gate
from app.services.gemini_prompt import ClipAnalysisMetadata


def _base_analysis(*, expected_mechanics: GeminiExpectedMechanics | None = None) -> GeminiClipAnalysis:
    payload: dict = {
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
    if expected_mechanics is not None:
        payload["expected_mechanics"] = expected_mechanics
    return GeminiClipAnalysis.model_validate(payload)


def _valid_em() -> GeminiExpectedMechanics:
    return GeminiExpectedMechanics(
        trick_name="Kickflip",
        overview="Because you tagged this as a kickflip: " + "x" * 40,
        checkpoints=[
            GeminiExpectedMechanicsCheckpoint(
                expected="Front foot slides up the deck then flicks off the nose pocket with ankle extension.",
                observed="In your clip the front foot lifts but the flick angle looks shallow before the board starts to flip.",
                impact="That likely caused under-rotation and a late catch window.",
            ),
            GeminiExpectedMechanicsCheckpoint(
                expected="Back foot pops straight down through the ball of the foot for height.",
                observed="The tail motion is visible; pop timing looks slightly ahead of the flick.",
                impact="The timing gap can make the board rocket or flatten the flip arc.",
            ),
        ],
        best_next_try="Prioritize a slightly later flick after the tail leaves the ground, keeping shoulders level.",
        drill="Ten slow stationary kickflip attempts filming the feet from the side.",
    )


def test_gate_keeps_valid_block_for_tagged_registry_trick() -> None:
    meta = ClipAnalysisMetadata.from_job_upload(
        video_path="/x.mp4",
        clip_label="c",
        stance="regular",
        obstacle="flat",
        tricks=["kickflip"],
        duration_seconds=3.0,
        mime_type="video/mp4",
        first_pass_readiness="usable",
    )
    a = _base_analysis(expected_mechanics=_valid_em())
    out = apply_expected_mechanics_gate(a, meta)
    assert out.expected_mechanics is not None
    assert out.expected_mechanics.trick_name == "Kickflip"


def test_gate_drops_when_no_user_trick() -> None:
    meta = ClipAnalysisMetadata.all_unknown()
    a = _base_analysis(expected_mechanics=_valid_em())
    out = apply_expected_mechanics_gate(a, meta)
    assert out.expected_mechanics is None


def test_gate_drops_unsupported_trick_string() -> None:
    meta = ClipAnalysisMetadata.from_job_upload(
        video_path="/x.mp4",
        clip_label="c",
        stance="regular",
        obstacle="flat",
        tricks=["my custom made-up trick xyz"],
        duration_seconds=3.0,
        mime_type="video/mp4",
    )
    a = _base_analysis(expected_mechanics=_valid_em())
    out = apply_expected_mechanics_gate(a, meta)
    assert out.expected_mechanics is None


def test_gate_drops_trick_detection_phrase() -> None:
    meta = ClipAnalysisMetadata.from_job_upload(
        video_path="/x.mp4",
        clip_label="c",
        stance="regular",
        obstacle="flat",
        tricks=["kickflip"],
        duration_seconds=3.0,
        mime_type="video/mp4",
    )
    em = _valid_em()
    bad = em.model_copy(
        update={
            "overview": em.overview + " We detected a kickflip in this clip.",
        }
    )
    a = _base_analysis(expected_mechanics=bad)
    out = apply_expected_mechanics_gate(a, meta)
    assert out.expected_mechanics is None


def test_gate_drops_insufficient_readiness() -> None:
    meta = ClipAnalysisMetadata.from_job_upload(
        video_path="/x.mp4",
        clip_label="c",
        stance="regular",
        obstacle="flat",
        tricks=["kickflip"],
        duration_seconds=3.0,
        mime_type="video/mp4",
        first_pass_readiness="insufficient",
    )
    a = _base_analysis(expected_mechanics=_valid_em())
    out = apply_expected_mechanics_gate(a, meta)
    assert out.expected_mechanics is None
