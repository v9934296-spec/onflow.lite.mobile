from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

# Canonical job statuses (API + storage). No aliases.
JobStatus = Literal["pending", "processing", "completed", "failed"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ClipJobRecord:
    id: str
    user_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    input_reference: str
    failure_reason: str | None
    result_json: dict[str, Any] | None
    clip_label: str
    tier: str
    clip_metadata: dict[str, Any]
    quota_source: str | None = None

    @staticmethod
    def new_pending(
        job_id: str,
        user_id: str,
        input_reference: str,
        *,
        clip_label: str = "untagged",
        tier: str = "free",
        clip_metadata: dict[str, Any] | None = None,
        quota_source: str | None = None,
    ) -> ClipJobRecord:
        now = utcnow()
        meta = dict(clip_metadata) if clip_metadata else {}
        tier_norm = tier if tier in ("free", "pro") else "free"
        return ClipJobRecord(
            id=job_id,
            user_id=user_id,
            status="pending",
            created_at=now,
            updated_at=now,
            input_reference=input_reference,
            failure_reason=None,
            result_json=None,
            clip_label=clip_label.strip() or "untagged",
            tier=tier_norm,
            clip_metadata=meta,
            quota_source=quota_source,
        )

    def with_status(
        self,
        status: JobStatus,
        *,
        failure_reason: str | None = None,
        result_json: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.updated_at = utcnow()
        if status == "completed":
            self.failure_reason = None
            self.result_json = result_json
        elif status == "failed":
            self.failure_reason = failure_reason or "unknown"
            self.result_json = None
        else:
            if failure_reason is not None:
                self.failure_reason = failure_reason
            if result_json is not None:
                self.result_json = result_json
