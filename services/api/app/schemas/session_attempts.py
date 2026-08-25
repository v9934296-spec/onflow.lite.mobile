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


SessionAttemptRejectReason = Literal[
    "missing_id",
    "invalid_logged_at",
    "session_not_found",
    "forbidden",
    # Immutability contract — the stored attempt was left untouched.
    "attempt_deleted",
    "session_immutable",
    "outcome_immutable",
    "attempt_immutable",
    "duplicate_in_batch",
]


class SessionAttemptRejected(BaseModel):
    id: str
    reason: SessionAttemptRejectReason = Field(
        description=(
            "Machine-readable cause. Clients branch on this value and never on prose."
        )
    )


class SessionAttemptSyncResponse(BaseModel):
    accepted: list[str]
    rejected: list[SessionAttemptRejected]


class SessionAttemptListResponse(BaseModel):
    attempts: list[SessionAttemptOut]
