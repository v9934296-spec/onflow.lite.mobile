from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NormalizedReviewPayload(BaseModel):
    """Stable mobile-friendly slice derived from Gemini output."""

    summary: str
    score: int | None = Field(default=None, ge=0, le=10)
    label: str | None = None
    what_you_did_right: list[str] = Field(default_factory=list)
    what_to_fix: list[str] = Field(default_factory=list)
    drill: str | None = None
    model: Literal["gemini"] = "gemini"


class CreateJobResponse(BaseModel):
    job_id: str
    status: Literal["pending"]


class MechanicsDimensionPayload(BaseModel):
    name: str
    score: float | None = Field(default=None, ge=0.0, le=10.0)
    assessment: str
    evidence: str | None = None


class QualitySignalsPayload(BaseModel):
    duration_seconds: float | None = None
    frames_sampled: int = 0
    motion_detected: bool = False
    video_readable: bool = False
    fps: float | None = None
    frame_count_estimated: int | None = None
    mean_brightness_0_1: float | None = None
    laplacian_var_mean: float | None = None
    mechanics_dimensions: list[MechanicsDimensionPayload] = Field(default_factory=list)


class ActionableCuePayload(BaseModel):
    cue: str
    why_it_matters: str
    drill: str | None = None


class SkateClipReviewBlockPayload(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    improvement_areas: list[str] = Field(default_factory=list)
    actionable_cues: list[ActionableCuePayload] = Field(default_factory=list)


class ExpectedMechanicsCheckpointPayload(BaseModel):
    expected: str
    observed: str
    impact: str


class ExpectedMechanicsPayload(BaseModel):
    trick_name: str
    overview: str
    checkpoints: list[ExpectedMechanicsCheckpointPayload] = Field(min_length=2, max_length=4)
    best_next_try: str
    drill: str | None = None


class AttemptCompareLatestPayload(BaseModel):
    job_id: str
    landed: str | None = None
    review_readiness: str | None = None
    primary_issue_key: str | None = None
    primary_issue_label: str | None = None
    best_cue: str | None = None
    best_drill: str | None = None
    technical_limit_summary: str | None = None
    created_at: str | None = None


class AttemptComparePreviousPayload(BaseModel):
    job_id: str
    landed: str | None = None
    review_readiness: str | None = None
    primary_issue_key: str | None = None
    primary_issue_label: str | None = None
    best_cue: str | None = None
    best_drill: str | None = None
    created_at: str | None = None


class SessionRecapTrickBreakdownPayload(BaseModel):
    trick_name: str
    attempts: int
    landed_count: int | None = None
    unclear_count: int | None = None
    primary_repeated_issue: str | None = None
    best_cue: str | None = None


class SessionRecapPayload(BaseModel):
    recap_available: bool
    session_id: str
    started_at: str | None = None
    ended_at: str | None = None
    session_attempt_count: int
    trick_count: int
    trick_breakdown: list[SessionRecapTrickBreakdownPayload] = Field(default_factory=list)
    strongest_progress_area: str | None = None
    repeated_session_issue: str | None = None
    late_session_dropoff: str | None = None
    best_trick_of_session: str | None = None
    session_summary: str
    next_session_focus: str
    recommended_drill: str | None = None


class AttemptComparePayload(BaseModel):
    compare_available: bool
    trick_name: str
    baseline_window_count: int
    latest_attempt: AttemptCompareLatestPayload | None = None
    previous_attempts: list[AttemptComparePreviousPayload] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    repeated_issues: list[str] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)
    compare_summary: str
    best_next_focus: str | None = None


class CoachingObservations(BaseModel):
    body_position: str | None = None
    foot_placement: str | None = None
    timing: str | None = None
    board_control: str | None = None
    commitment: str | None = None
    balance: str | None = None
    style_notes: str | None = None
    improvement_drill: str | None = None


class ClipResultPayload(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    analysis_type: Literal["skate_clip_review"] = "skate_clip_review"
    clip_label: str
    review_summary: str
    review_readiness: Literal["usable", "limited", "insufficient"]

    video_playback_url: str | None = None
    thumbnail_url: str | None = None

    quality_signals: QualitySignalsPayload
    observations: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    processing_notes: list[str] = Field(default_factory=list)
    skate_clip_review: SkateClipReviewBlockPayload | None = None
    coaching: CoachingObservations | None = None
    landed: Literal["yes", "no", "unclear"] | None = None
    land_score: float | None = Field(default=None, ge=0.0, le=10.0)
    primary_issue_key: str | None = None
    primary_issue_label: str | None = None
    best_cue: str | None = None
    best_drill: str | None = None
    review_method: str | None = None
    gemini_used: bool | None = None
    technical_limit_summary: str | None = None
    first_actionable_cue_shown: str | None = None
    first_drill_shown: str | None = None
    normalized_review: NormalizedReviewPayload | None = None
    expected_mechanics: ExpectedMechanicsPayload | None = None
    attempt_compare: AttemptComparePayload | None = None
    session_recap: SessionRecapPayload | None = None


class JobPendingResponse(BaseModel):
    job_id: str
    status: Literal["pending"]
    updated_at: str


class JobProcessingResponse(BaseModel):
    job_id: str
    status: Literal["processing"]
    updated_at: str


class JobCompletedResponse(BaseModel):
    job_id: str
    status: Literal["completed"]
    updated_at: str
    result: ClipResultPayload


class JobFailedResponse(BaseModel):
    job_id: str
    status: Literal["failed"]
    updated_at: str
    failure_reason: str


class JobListItem(BaseModel):
    job_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    clip_label: str
    updated_at: str
    failure_reason: str | None = None
    video_playback_url: str | None = None
    thumbnail_url: str | None = None


class ClipInitiateUploadRequest(BaseModel):
    session_id: str | None = None
    duration_seconds: float = Field(gt=0, le=30)
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    content_type: Literal["video/mp4", "video/quicktime"]
    size_bytes: int = Field(gt=0, le=100 * 1024 * 1024)
    client_hint_trick_id: str | None = None


class ClipInitiateUploadResponse(BaseModel):
    clip_id: str
    upload_url: str
    upload_method: Literal["PUT"] = "PUT"
    upload_expires_at: str
    storage_key: str


class ClipResponse(BaseModel):
    id: str
    user_id: str
    session_id: str | None = None
    upload_status: str
    storage_key: str
    duration_seconds: float | None = None
    width_px: int | None = None
    height_px: int | None = None
    content_type: str | None = None
    trick_id: str | None = None
    thumbnail_url: str | None = None
    landed: bool | None = None
    pte_rating: int | None = None
    created_at: str
    updated_at: str


class ClipCompleteUploadResponse(ClipResponse):
    estimated_analysis_completion_at: str | None = None