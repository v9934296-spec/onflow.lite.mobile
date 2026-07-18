from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SessionAttemptIn(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    session_id: str = Field(min_length=1, max_length=36)
    trick_id: str = Field(min_length=1, max_length=64)
    canonical_name: str = Field(min_length=1, max_length=128)
    outcome: Literal["landed", "missed"]
    logged_at: str = Field(
        min_length=1,
        max_length=40,
        description="ISO-8601 timestamp from the client clock.",
    )


class SessionAttemptOut(BaseModel):
    id: str
    session_id: str
    trick_id: str
    canonical_name: str
    outcome: Literal["landed", "missed"]
    logged_at: str


class SessionAttemptSyncRequest(BaseModel):
    attempts: list[SessionAttemptIn] = Field(default_factory=list, max_length=100)


class SessionAttemptRejected(BaseModel):
    id: str
    reason: str


class SessionAttemptSyncResponse(BaseModel):
    accepted: list[str]
    rejected: list[SessionAttemptRejected]


class SessionAttemptListResponse(BaseModel):
    attempts: list[SessionAttemptOut]
