from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.clips import SessionRecapPayload


class SessionCreateRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


class SessionCreateResponse(BaseModel):
    user_id: str
    session_token: str
    email: str


# --- Stats API (progression memory, compare, sessions) ---


class StatsTrickAttemptRow(BaseModel):
    job_id: str
    landed: str | None
    stance: str
    obstacle: str
    review_readiness: str
    created_at: str
    primary_issue_key: str | None = None
    primary_issue_label: str | None = None
    best_cue: str | None = None
    best_drill: str | None = None
    review_method: str | None = None
    gemini_used: bool | None = None
    technical_limit_summary: str | None = None


class CompareTrend(BaseModel):
    last_5_landed_yes: int
    last_5_landed_no: int
    last_5_unclear: int
    last_5_usable: int
    last_5_limited: int
    last_5_insufficient: int


class TrickCompareResponse(BaseModel):
    trick_name: str
    compare_available: bool
    latest_attempt: StatsTrickAttemptRow | None
    baseline_window_count: int
    repeated_issue_keys: list[str]
    improving_issue_keys: list[str]
    stable_strength_summary: str | None
    compare_summary: str
    trend: CompareTrend


class SessionBestMake(BaseModel):
    trick_name: str
    job_id: str
    created_at: str
    best_cue: str | None


class SessionSummaryResponse(BaseModel):
    session_id: str
    total_attempts: int
    tricks_attempted_count: int
    most_attempted_trick: str | None
    makes: int
    misses: int
    unclear: int
    usable_clips: int
    limited_clips: int
    insufficient_clips: int
    best_make: SessionBestMake | None
    weakest_pattern_key: str | None
    weakest_pattern_label: str | None
    what_improved_today: str | None
    what_to_practice_next_session: str | None
    summary: str
    summary_confidence: Literal["usable", "limited"]
    session_recap: SessionRecapPayload | None = None
