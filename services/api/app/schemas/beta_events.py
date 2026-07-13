from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ClientBetaEventKind = Literal[
    "result_viewed",
    "upload_submitted",
    "analyzing_entered",
    "quick_feedback_submitted",
    "full_feedback_opened",
    "share_initiated",
    "share_completed",
    "share_failed",
    "share_install_attributed",
]


class ClientBetaEventRequest(BaseModel):
    kind: ClientBetaEventKind
    job_id: str | None = Field(default=None, max_length=80)
    share_target: str | None = Field(default=None, max_length=32)
    error_detail: str | None = Field(default=None, max_length=2000)
    ref_source: str | None = Field(default=None, max_length=32)


class ClientBetaEventResponse(BaseModel):
    ok: bool = True
