"""
Map validated Gemini analysis + video sanity metrics into the mobile-facing result contract.
"""
from __future__ import annotations

from typing import Any, Literal

from app.schemas.clips import NormalizedReviewPayload
from app.schemas.gemini_analysis import GeminiClipAnalysis
from app.services.landing_status import resolve_landed_status
from app.services.progression_memory import compute_progression_fields
from app.services.review_normalize import normalize_review

Readiness = Literal["usable", "limited", "insufficient"]

RESULT_SCHEMA_VERSION = 1


def _round_score(x: float | None) -> float | None:
    if x is None:
        return None
    return round(float(x) + 1e-9, 1)


def build_completed_result_from_gemini(
    gemini: GeminiClipAnalysis,
    first_pass: dict[str, Any],
    clip_label: str,
    gemini_enrichment: dict[str, Any] | None = None,
    *,
    enrichment_attempted: bool = False,
    trick: str = "",
    stance: str = "",
    enrichment_model: str | None = None,
    review_model: str = "gemini",
) -> dict[str, Any]:
    """
    Produces the persisted `result_json` for completed jobs.
    Video fields come from first_pass (OpenCV); mechanics content from Gemini only.
    """
    label = clip_label.strip() or "untagged"
    readiness = first_pass.get("review_readiness")
    if readiness not in ("usable", "limited", "insufficient"):
        readiness = "limited"

    qs_video: dict[str, Any] = {
        "duration_seconds": first_pass.get("duration_seconds"),
        "frames_sampled": int(first_pass.get("frames_sampled") or 0),
        "motion_detected": bool(first_pass.get("motion_detected")),
        "video_readable": bool(first_pass.get("video_readable")),
        "fps": first_pass.get("fps"),
        "frame_count_estimated": first_pass.get("frame_count_estimated"),
        "mean_brightness_0_1": first_pass.get("mean_brightness_0_1"),
        "mechanics_dimensions": [
            {
                "name": sig.name,
                "score": _round_score(sig.score),
                "assessment": sig.assessment,
                "evidence": sig.evidence,
            }
            for sig in gemini.quality_signals
        ],
    }
    lv = first_pass.get("laplacian_var_mean")
    if isinstance(lv, (int, float)):
        qs_video["laplacian_var_mean"] = round(float(lv), 2)

    observations: list[str] = []
    for line in first_pass.get("observations") or []:
        if isinstance(line, str) and line.strip():
            observations.append(f"[Video pass] {line.strip()}")
    for o in gemini.observations:
        observations.append(f"{o.title}: {o.detail} [{o.severity}]")

    uncertainty_notes = [u.strip() for u in gemini.uncertainty_notes if u and str(u).strip()]

    processing_notes: list[str] = list(gemini.processing_notes)
    if review_model == "pegasus":
        processing_notes.append(
            "Canonical analysis uses Twelve Labs Pegasus on your clip — mechanics and "
            "visibility only, not automated trick naming or judging."
        )
    else:
        processing_notes.append(
            "Canonical analysis uses Google Gemini on your clip — mechanics and visibility only, "
            "not automated trick naming or judging."
        )

    skate_clip_review = {
        "strengths": list(gemini.strengths),
        "improvement_areas": list(gemini.improvement_areas),
        "actionable_cues": [
            {
                "cue": c.cue,
                "why_it_matters": c.why_it_matters,
                "drill": c.drill,
            }
            for c in gemini.actionable_cues
        ],
    }

    review_summary = gemini.review_summary.strip()

    coaching: dict[str, str] | None = None
    enrichment_landed: object = None
    if gemini_enrichment:
        add = gemini_enrichment.get("review_addendum", "")
        if isinstance(add, str) and add.strip():
            review_summary = (
                f"{review_summary} {add.strip()}".strip() if review_summary else add.strip()
            )
        for b in gemini_enrichment.get("observation_bullets") or []:
            if isinstance(b, str) and b.strip():
                observations.append(b.strip())
        raw_coaching = gemini_enrichment.get("coaching")
        if isinstance(raw_coaching, dict):
            coaching = {k: v for k, v in raw_coaching.items() if v is not None}
            if not coaching:
                coaching = None
        enrichment_landed = gemini_enrichment.get("landed")
    primary_landed = first_pass.get("landed")
    landed = resolve_landed_status(primary_landed, enrichment_landed)


    if enrichment_attempted and gemini_enrichment is None:
        processing_notes = list(processing_notes)
        processing_notes.append("Supplementary narrative did not complete for this clip.")

    if enrichment_model:
        processing_notes = list(processing_notes)
        processing_notes.append(f"Enrichment model: {enrichment_model}.")

    prog = compute_progression_fields(
        gemini,
        first_pass,
        gemini_enrichment,
        uncertainty_notes=uncertainty_notes,
        processing_notes=processing_notes,
    )

    first_actionable_cue_shown: str | None = None
    first_drill_shown: str | None = None
    if gemini.actionable_cues:
        c0 = gemini.actionable_cues[0]
        if c0.cue and str(c0.cue).strip():
            first_actionable_cue_shown = str(c0.cue).strip()
        if c0.drill and str(c0.drill).strip():
            first_drill_shown = str(c0.drill).strip()
    if coaching and isinstance(coaching.get("improvement_drill"), str):
        idrill = coaching["improvement_drill"].strip()
        if idrill and not first_drill_shown:
            first_drill_shown = idrill

    nr_raw = normalize_review(
        gemini, trick, stance, enrichment=gemini_enrichment, model=review_model
    )
    normalized_review = NormalizedReviewPayload.model_validate(nr_raw).model_dump()

    expected_mechanics: dict[str, Any] | None = None
    if gemini.expected_mechanics is not None:
        expected_mechanics = gemini.expected_mechanics.model_dump()

    out: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "analysis_type": "skate_clip_review",
        "clip_label": label,
        "review_summary": review_summary,
        "review_readiness": readiness,
        "quality_signals": qs_video,
        "observations": observations,
        "uncertainty_notes": uncertainty_notes,
        "processing_notes": processing_notes,
        "skate_clip_review": skate_clip_review,
        "coaching": coaching,
        "landed": landed,
        "land_score": gemini.land_score if landed == "yes" else None,
        "first_actionable_cue_shown": first_actionable_cue_shown,
        "first_drill_shown": first_drill_shown,
        "normalized_review": normalized_review,
        **prog,
    }
    if expected_mechanics is not None:
        out["expected_mechanics"] = expected_mechanics
    return out


def build_degraded_provider_failure_result(
    first_pass: dict[str, Any],
    clip_label: str,
    *,
    pipeline_reason: str,
    pipeline_detail: str = "",
) -> dict[str, Any]:
    """
    Honest completed-job payload when the main Gemini pipeline could not run or finish.

    Uses first-pass video metrics only — no mechanics review, cues, or normalized_review.
    """
    label = clip_label.strip() or "untagged"
    readiness: Readiness = "insufficient"
    detail = (pipeline_detail or "").strip()
    if len(detail) > 400:
        detail = detail[:399] + "…"
    reason = (pipeline_reason or "unknown").strip() or "unknown"

    qs: dict[str, Any] = {
        "duration_seconds": first_pass.get("duration_seconds"),
        "frames_sampled": int(first_pass.get("frames_sampled") or 0),
        "motion_detected": bool(first_pass.get("motion_detected")),
        "video_readable": bool(first_pass.get("video_readable")),
        "fps": first_pass.get("fps"),
        "frame_count_estimated": first_pass.get("frame_count_estimated"),
        "mean_brightness_0_1": first_pass.get("mean_brightness_0_1"),
        "mechanics_dimensions": [],
    }
    lv = first_pass.get("laplacian_var_mean")
    if isinstance(lv, (int, float)):
        qs["laplacian_var_mean"] = round(float(lv), 2)

    observations: list[str] = []
    for line in first_pass.get("observations") or []:
        if isinstance(line, str) and line.strip():
            observations.append(f"[Video pass] {line.strip()}")

    proc: list[str] = [
        "Automated video checks only below; the AI review service did not return a usable analysis for this clip.",
        f"Pipeline reason code: {reason}.",
    ]
    if detail:
        proc.append(f"Detail (truncated if long): {detail}")

    uncertainty: list[str] = [
        "Full mechanics review was not generated; only technical video signals are available.",
    ]

    summary = (
        "We could not complete AI review for this clip (the review service did not finish). "
        "What you see below is from our automated video check only — not a trick assessment."
    )

    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "analysis_type": "skate_clip_review",
        "clip_label": label,
        "review_summary": summary,
        "review_readiness": readiness,
        "quality_signals": qs,
        "observations": observations,
        "uncertainty_notes": uncertainty,
        "processing_notes": proc,
        "skate_clip_review": None,
        "coaching": None,
        "landed": None,
        "first_actionable_cue_shown": None,
        "first_drill_shown": None,
        "normalized_review": None,
        "review_method": "provider_unavailable",
        "gemini_used": False,
        "technical_limit_summary": None,
        "primary_issue_key": None,
        "primary_issue_label": None,
        "best_cue": None,
        "best_drill": None,
    }


def assemble_clip_review_result(
    first: dict[str, Any],
    clip_label: str,
    gemini_enrichment: dict[str, Any] | None,
    *,
    gemini_attempted: bool,
) -> dict[str, Any]:
    """Simplified assembly for unit tests and legacy callers (no main Gemini analysis block)."""
    label = clip_label.strip() or "untagged"
    readiness = first.get("review_readiness")
    if readiness not in ("usable", "limited", "insufficient"):
        readiness = "insufficient"

    review_summary = (first.get("review_summary_base") or "").strip()
    observations = [
        x.strip()
        for x in (first.get("observations") or [])
        if isinstance(x, str) and x.strip()
    ]
    processing_notes = [
        x.strip()
        for x in (first.get("processing_notes") or [])
        if isinstance(x, str) and x.strip()
    ]

    coaching: dict[str, str] | None = None
    enrichment_landed: object = None
    if gemini_enrichment:
        add = gemini_enrichment.get("review_addendum", "")
        if isinstance(add, str) and add.strip():
            review_summary = (
                f"{review_summary} {add.strip()}".strip() if review_summary else add.strip()
            )
        for b in gemini_enrichment.get("observation_bullets") or []:
            if isinstance(b, str) and b.strip():
                observations.append(b.strip())
        raw_coaching = gemini_enrichment.get("coaching")
        if isinstance(raw_coaching, dict):
            coaching = {k: v for k, v in raw_coaching.items() if v is not None}
            if not coaching:
                coaching = None
        enrichment_landed = gemini_enrichment.get("landed")
    primary_landed = first.get("landed")
    landed = resolve_landed_status(primary_landed, enrichment_landed)


    if gemini_attempted and gemini_enrichment is None:
        processing_notes = list(processing_notes)
        processing_notes.append("Supplementary narrative did not complete for this clip.")

    prog = compute_progression_fields(
        None,
        first,
        gemini_enrichment,
        uncertainty_notes=[],
        processing_notes=processing_notes,
    )

    first_actionable_cue_shown: str | None = None
    first_drill_shown: str | None = None
    if coaching and isinstance(coaching.get("improvement_drill"), str):
        idrill = coaching["improvement_drill"].strip()
        if idrill:
            first_drill_shown = idrill

    raw_partial: dict[str, Any] = {
        "review_summary": review_summary,
        "strengths": [],
        "improvement_areas": [],
        "actionable_cues": [],
        "quality_signals": [],
    }
    if coaching:
        raw_partial["coaching"] = coaching
    nr_raw = normalize_review(raw_partial, "", "", enrichment=gemini_enrichment)
    normalized_review = NormalizedReviewPayload.model_validate(nr_raw).model_dump()

    quality_signals: dict[str, Any] = {
        "duration_seconds": first.get("duration_seconds"),
        "frames_sampled": int(first.get("frames_sampled") or 0),
        "motion_detected": bool(first.get("motion_detected")),
        "video_readable": bool(first.get("video_readable")),
        "fps": first.get("fps"),
        "frame_count_estimated": first.get("frame_count_estimated"),
        "mean_brightness_0_1": first.get("mean_brightness_0_1"),
        "mechanics_dimensions": [],
    }
    lv = first.get("laplacian_var_mean")
    if isinstance(lv, (int, float)):
        quality_signals["laplacian_var_mean"] = round(float(lv), 2)

    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "analysis_type": "skate_clip_review",
        "clip_label": label,
        "review_summary": review_summary,
        "review_readiness": readiness,
        "quality_signals": quality_signals,
        "observations": observations,
        "uncertainty_notes": [],
        "processing_notes": processing_notes,
        "skate_clip_review": None,
        "coaching": coaching,
        "landed": landed,
        "first_actionable_cue_shown": first_actionable_cue_shown,
        "first_drill_shown": first_drill_shown,
        "normalized_review": normalized_review,
        **prog,
    }
