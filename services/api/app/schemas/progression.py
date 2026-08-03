"""Pydantic schemas for the progression timeline (Step 5F).

The timeline is a *personal* skating history — lightweight session previews,
newest-first. It is intentionally NOT the full recap payload (see 5E for that).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProgressionTimelineItem(BaseModel):
    """One session preview in the progression timeline. Lightweight by design."""

    session_id: str
    ended_at: str | None = None
    spot: str | None = None
    focus_trick: str | None = None
    duration_seconds: int | None = None
    clips_count: int = 0
    attempt_count: int = 0
    best_pte_score: float | None = None
    thumbnail_url: str | None = None


class ProgressionTimelineResponse(BaseModel):
    """Owner-scoped, offset-paginated progression history (newest-first)."""

    items: list[ProgressionTimelineItem] = Field(default_factory=list)
    page: int
    page_size: int
    has_more: bool
