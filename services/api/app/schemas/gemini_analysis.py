"""
Strict Pydantic models for Gemini JSON output (validated before any job completion).
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


class GeminiQualitySignal(BaseModel):
    name: Literal[
        "balance",
        "stability",
        "timing",
        "landing_control",
        "body_alignment",
        "pop_explosion",
        "board_control",
    ]
    score: float | None = Field(default=None, ge=0.0, le=10.0)
    assessment: str = Field(min_length=1, max_length=240)
    evidence: str | None = Field(default=None, max_length=400)

    @field_validator("score", mode="before")
    @classmethod
    def coerce_score_precision(cls, v: object) -> float | None:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            x = float(v)
            return round(x + 1e-9, 1)
        return v


class GeminiObservation(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    detail: str = Field(min_length=1, max_length=500)
    severity: Literal["info", "good", "warning"] = "info"


class GeminiActionableCue(BaseModel):
    cue: str = Field(min_length=1, max_length=200)
    why_it_matters: str = Field(min_length=1, max_length=300)
    drill: str | None = Field(default=None, max_length=240)


_Strengths = Annotated[list[str], Field(min_length=1, max_length=5)]
_Improvements = Annotated[list[str], Field(min_length=1, max_length=5)]
_ActionCues = Annotated[list[GeminiActionableCue], Field(min_length=1, max_length=6)]
_Observations = Annotated[list[GeminiObservation], Field(min_length=1, max_length=8)]


class GeminiExpectedMechanicsCheckpoint(BaseModel):
    """Expected vs observed — framed as user-tagged context, not trick detection."""

    expected: str = Field(min_length=8, max_length=420)
    observed: str = Field(min_length=8, max_length=420)
    impact: str = Field(min_length=8, max_length=320)


class GeminiExpectedMechanics(BaseModel):
    """
    Optional comparison block when the skater tagged a supported trick.
    Omitted when evidence is weak or the trick is not in the registry.
    """

    trick_name: str = Field(min_length=2, max_length=80)
    overview: str = Field(min_length=40, max_length=900)
    checkpoints: list[GeminiExpectedMechanicsCheckpoint] = Field(min_length=2, max_length=4)
    best_next_try: str = Field(min_length=20, max_length=420)
    drill: str | None = Field(default=None, max_length=320)


class GeminiClipAnalysis(BaseModel):
    review_summary: str = Field(min_length=20, max_length=1200)
    strengths: _Strengths
    improvement_areas: _Improvements
    actionable_cues: _ActionCues
    observations: _Observations
    quality_signals: list[GeminiQualitySignal] = Field(default_factory=list)
    land_score: float | None = Field(default=None, ge=0.0, le=10.0)
    uncertainty_notes: list[str] = Field(default_factory=list)
    processing_notes: list[str] = Field(default_factory=list)
    expected_mechanics: GeminiExpectedMechanics | None = None

    @field_validator("land_score", mode="before")
    @classmethod
    def _round_land_score(cls, v: object) -> float | None:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return round(float(v) + 1e-9, 1)
        return v
