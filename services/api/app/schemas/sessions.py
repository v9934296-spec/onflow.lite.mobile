"""Pydantic schemas for V1 skating session endpoints (contracts §3)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    spot_label: str | None = None
    focus_trick: str | None = None
    notes: str | None = None
    started_at: datetime | None = None


class SessionUpdate(BaseModel):
    ended_at: datetime | None = None
    breakthrough_note: str | None = None
    spot_label: str | None = None
    focus_trick: str | None = None
    notes: str | None = None


class SessionParticipantResponse(BaseModel):
    user_id: str
    username: str | None = None
    tag_name: str | None = None
    profile_photo_url: str | None = None


class SessionClipSummary(BaseModel):
    id: str
    trick_id: str | None = None
    trick_display: str | None = None
    thumbnail_url: str | None = None
    landed: bool | None = None
    pte_rating: int | None = None
    created_at: str
    is_first_land: bool = False


class SessionResponse(BaseModel):
    id: str
    user_id: str
    spot_label: str | None = None
    focus_trick: str | None = None
    notes: str | None = None
    started_at: str
    ended_at: str | None = None
    breakthrough_note: str | None = None
    clip_count: int = 0
    attempt_count: int = 0
    participants: list[SessionParticipantResponse] = Field(default_factory=list)
    created_at: str
    updated_at: str | None = None
    clips: list[SessionClipSummary] | None = None


class SessionListItem(BaseModel):
    id: str
    spot_label: str | None = None
    focus_trick: str | None = None
    started_at: str
    ended_at: str | None = None
    clip_count: int = 0
    attempt_count: int = 0
    breakthrough_note: str | None = None
    tricks_attempted: list[str] = Field(default_factory=list)
    preview_thumbnail_url: str | None = None


class SessionListResponse(BaseModel):
    items: list[SessionListItem]
    next_cursor: str | None = None


class SessionParticipantAdd(BaseModel):
    user_id: str


class SessionRecapClip(BaseModel):
    """One clip inside a session recap detail (Step 5E)."""

    clip_id: str
    thumbnail_url: str | None = None
    video_playback_url: str | None = None
    trick: str | None = None
    stance: str | None = None
    landed: bool | None = None
    pte_score: int | None = None
    created_at: str


class SessionRecapDetailResponse(BaseModel):
    """Aggregated session recap for the progression detail view (Step 5E).

    Metrics use existing data only. When a metric cannot be derived honestly it is
    ``null`` rather than a guessed value. Clips are ordered newest-first.
    """

    session_id: str
    started_at: str
    ended_at: str | None = None
    duration_seconds: int | None = None
    spot: str | None = None
    focus_trick: str | None = None
    clips_count: int = 0
    attempts_count: int = 0
    landed_count: int | None = None
    landed_rate: float | None = None
    best_pte_score: float | None = None
    average_pte_score: float | None = None
    breakthrough_note: str | None = None
    clips: list[SessionRecapClip] = Field(default_factory=list)
