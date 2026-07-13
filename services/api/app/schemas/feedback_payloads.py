from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FeedbackCreateRequest(BaseModel):
    useful: bool | None = None
    accurate_enough: bool | None = None
    issue_kind: Literal["technical", "analysis_mismatch", "other"] | None = None
    note: str = Field(default="", max_length=4000)
    job_id: str | None = Field(None, max_length=64)
    client_kind: str | None = Field(None, max_length=64)
    coaching_helped_next_try: bool | None = None
    coaching_too_generic: bool | None = None
    coaching_wrong_read: bool | None = None
    best_cue_clear: bool | None = None

    @model_validator(mode="after")
    def note_or_structured_signal(self) -> "FeedbackCreateRequest":
        has_note = bool(self.note.strip())
        has_structured = any(
            x is not None
            for x in (
                self.useful,
                self.accurate_enough,
                self.coaching_helped_next_try,
                self.coaching_too_generic,
                self.coaching_wrong_read,
                self.best_cue_clear,
            )
        )
        if not has_note and not has_structured:
            raise ValueError("Provide a note or at least one rating / coaching flag.")
        return self


class FeedbackCreateResponse(BaseModel):
    feedback_id: str
