from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

# Canonical job statuses (API + storage). No aliases.
JobStatus = Literal["pending", "processing", "completed", "failed"]


class JobAlreadyExists(Exception):
    """Raised when insert races on the same job/clip primary key."""


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
    claim_token: str | None = None
    claimed_at: datetime | None = None
    lease_expires_at: datetime | None = None
    attempt_number: int = 0

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
            self.claim_token = None
            self.claimed_at = None
            self.lease_expires_at = None
        elif status == "failed":
            self.failure_reason = failure_reason or "unknown"
            self.result_json = None
            self.claim_token = None
            self.claimed_at = None
            self.lease_expires_at = None
        else:
            if failure_reason is not None:
                self.failure_reason = failure_reason
            if result_json is not None:
                self.result_json = result_json

    def take_lease(self, *, lease_seconds: int) -> str:
        """Mark this job processing under a new exclusive lease; return claim token."""
        import uuid

        now = utcnow()
        token = str(uuid.uuid4())
        self.status = "processing"
        self.updated_at = now
        self.claimed_at = now
        self.claim_token = token
        self.attempt_number = int(self.attempt_number or 0) + 1
        from datetime import timedelta

        self.lease_expires_at = now + timedelta(seconds=max(1, lease_seconds))
        return token

    def lease_is_live(
        self,
        *,
        now: datetime | None = None,
        lease_seconds: int | None = None,
    ) -> bool:
        """True while another worker still owns this processing job."""
        if self.status != "processing":
            return False
        current = now or utcnow()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)

        expires = self.lease_expires_at
        if expires is not None:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            return expires > current

        # Legacy / unleased processing rows: treat updated_at + timeout as a soft lease
        # so deploy-time NULL leases are not immediately reclaimable.
        if lease_seconds is None:
            from app.core.config import get_settings

            lease_seconds = max(1, int(get_settings().arq_job_timeout))
        updated = self.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return (current - updated).total_seconds() < max(1, lease_seconds)
