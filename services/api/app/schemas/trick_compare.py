"""Trick clip comparison (Step 5G) — oldest vs newest analyzed clip for one trick."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TrickCompareClip(BaseModel):
    clip_id: str
    session_id: str | None = None
    thumbnail_url: str | None = None
    video_playback_url: str | None = None
    pte_score: int | None = None
    landed: bool | None = None
    created_at: str


class TrickClipCompareResponse(BaseModel):
    trick_name: str
    trick_display: str
    compare_available: bool
    days_between: int | None = None
    pte_delta: int | None = None
    oldest_landed: bool | None = None
    newest_landed: bool | None = None
    oldest_clip: TrickCompareClip | None = None
    newest_clip: TrickCompareClip | None = None
    progress_notes: list[str] = Field(default_factory=list)
    clips_count: int = 0
