from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# Product funnel + legacy beta/share kinds. Keep in sync with client AnalyticsEvent
# and share flow. Unknown kinds are rejected so the table stays queryable.
ALLOWED_CLIENT_EVENT_KINDS: frozenset[str] = frozenset(
    {
        # Legacy beta / share
        "result_viewed",
        "upload_submitted",
        "analyzing_entered",
        "quick_feedback_submitted",
        "full_feedback_opened",
        "share_initiated",
        "share_completed",
        "share_failed",
        "share_install_attributed",
        # Client product analytics (src/analytics.ts)
        "home_viewed",
        "clip_film_started",
        "trick_selected",
        "session_attempt_logged",
        "session_ended",
        "session_recap_viewed",
        "session_history_viewed",
        "session_history_opened",
        "feed_viewed",
        "paywall_viewed",
        "notifications_viewed",
        "capture_completed",
        "capture_failed",
        "land_reported",
        "log_viewed",
        "log_exported",
        "log_cleared",
        "storage_error",
        "account_export_requested",
        "account_delete_requested",
    }
)


class ClientBetaEventRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=64)
    job_id: str | None = Field(default=None, max_length=80)
    share_target: str | None = Field(default=None, max_length=32)
    error_detail: str | None = Field(default=None, max_length=2000)
    ref_source: str | None = Field(default=None, max_length=32)

    @field_validator("kind")
    @classmethod
    def _kind_allowlisted(cls, v: str) -> str:
        cleaned = (v or "").strip()
        if cleaned not in ALLOWED_CLIENT_EVENT_KINDS:
            raise ValueError(f"Unsupported event kind: {cleaned!r}")
        return cleaned


class ClientBetaEventResponse(BaseModel):
    ok: bool = True
