"""Feed API schemas (contracts §8)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FeedUserResponse(BaseModel):
    user_id: str
    username: str
    tag_name: str
    profile_photo_url: str | None = None
    tier: str = "flow"


class ReactionBucketResponse(BaseModel):
    count: int = 0
    viewer_reacted: bool = False
    reactor_user_ids: list[str] = Field(default_factory=list)


class ReactionsSummaryResponse(BaseModel):
    fire: ReactionBucketResponse = Field(default_factory=ReactionBucketResponse)
    saw_it: ReactionBucketResponse = Field(default_factory=ReactionBucketResponse)
    same_battle: ReactionBucketResponse = Field(default_factory=ReactionBucketResponse)
    progression: ReactionBucketResponse = Field(default_factory=ReactionBucketResponse)


class FeedEventItemResponse(BaseModel):
    id: str
    user: FeedUserResponse
    event_type: str
    event_version: str
    payload: dict[str, Any]
    generated_at: str
    reactions_summary: ReactionsSummaryResponse


class FeedListResponse(BaseModel):
    items: list[FeedEventItemResponse]
    next_cursor: str | None = None
    lifecycle_stage: str
