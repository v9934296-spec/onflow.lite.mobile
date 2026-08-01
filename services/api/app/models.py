"""SQLModel table definitions for clip jobs."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, Index, Text, text
from sqlmodel import Field, SQLModel, Session, select


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClipJobModel(SQLModel, table=True):
    """Persistent clip job record (Postgres or SQLite)."""

    __tablename__ = "clip_jobs"

    id: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    status: str = Field(index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    input_reference: str = ""
    failure_reason: Optional[str] = None
    result_json_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    clip_label: str = Field(default="untagged")
    tier: str = Field(default="free")
    quota_source: Optional[str] = Field(default=None)
    metadata_json: str = Field(default="{}", sa_column=Column(Text))
    claim_token: Optional[str] = Field(default=None, max_length=64)
    claimed_at: Optional[datetime] = Field(default=None)
    lease_expires_at: Optional[datetime] = Field(default=None)
    attempt_number: int = Field(default=0)

    @property
    def result_json(self) -> dict[str, Any] | None:
        if self.result_json_text is None:
            return None
        return json.loads(self.result_json_text)

    @result_json.setter
    def result_json(self, value: dict[str, Any] | None) -> None:
        self.result_json_text = json.dumps(value) if value is not None else None

    @property
    def clip_metadata(self) -> dict[str, Any]:
        try:
            m = json.loads(self.metadata_json) if self.metadata_json else {}
            return m if isinstance(m, dict) else {}
        except json.JSONDecodeError:
            return {}

    @clip_metadata.setter
    def clip_metadata(self, value: dict[str, Any]) -> None:
        self.metadata_json = json.dumps(value or {})


class TrickStatModel(SQLModel, table=True):
    """Per-trick attempt record — written after every completed job with a named trick."""

    __tablename__ = "trick_stats"

    id: str = Field(
        primary_key=True,
        default_factory=lambda: uuid.uuid4().hex[:16],
    )
    user_id: str = Field(index=True)
    job_id: str = Field(index=True)
    trick_name: str = Field(index=True)
    stance: str = ""
    obstacle: str = ""
    landed: Optional[str] = None  # "yes", "no", or None (unclear / not recorded)
    review_readiness: str = "insufficient"
    created_at: datetime = Field(default_factory=_utcnow)
    primary_issue_key: Optional[str] = None
    primary_issue_label: Optional[str] = None
    best_cue: Optional[str] = None
    best_drill: Optional[str] = None
    review_method: str = "first_pass_only"
    gemini_used: bool = False
    session_id: Optional[str] = None
    technical_limit_summary: Optional[str] = None
    land_score: Optional[float] = Field(default=None)


class MilestoneModel(SQLModel, table=True):
    """P.T.E. Tech 1.0 — unlocked milestone record."""

    __tablename__ = "milestones"

    id: str = Field(
        primary_key=True,
        default_factory=lambda: uuid.uuid4().hex[:16],
    )
    user_id: str = Field(index=True)
    milestone_key: str = Field(index=True)  # "first_make", "locked_in", etc.
    trick_name: Optional[str] = None  # which trick triggered it (None for non-trick milestones)
    session_id: Optional[str] = None  # which session triggered it (for session_grind, locked_in)
    job_id: Optional[str] = None  # which job triggered it (for line_landed)
    achieved_at: datetime = Field(default_factory=_utcnow)


class CustomLineModel(SQLModel, table=True):
    """P.T.E. Tech 1.0 — user-defined line (trick sequence) template."""

    __tablename__ = "custom_lines"

    id: str = Field(
        primary_key=True,
        default_factory=lambda: uuid.uuid4().hex[:16],
    )
    user_id: str = Field(index=True)
    line_name: str
    trick_sequence_json: str = Field(default="[]", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @property
    def trick_sequence(self) -> list[str]:
        try:
            seq = json.loads(self.trick_sequence_json or "[]")
            return seq if isinstance(seq, list) else []
        except (json.JSONDecodeError, TypeError):
            return []


class LineAttemptModel(SQLModel, table=True):
    """P.T.E. Tech 1.0 — recorded attempt of a custom line."""

    __tablename__ = "line_attempts"

    id: str = Field(
        primary_key=True,
        default_factory=lambda: uuid.uuid4().hex[:16],
    )
    user_id: str = Field(index=True)
    line_id: str = Field(index=True)
    job_id: str = Field(index=True)
    landed: Optional[str] = None
    session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


class UserModel(SQLModel, table=True):
    """User identity and billing state (migrated from SQLite)."""

    __tablename__ = "users"

    id: str = Field(primary_key=True, max_length=64)
    email: str = Field(index=True, max_length=256)
    tier: str = Field(default="trial", max_length=16)
    trial_started_at: Optional[datetime] = Field(default=None)
    trial_expires_at: Optional[datetime] = Field(default=None)
    subscription_status: str = Field(default="active", max_length=32)
    subscription_product_id: Optional[str] = Field(default=None, max_length=128)
    rc_app_user_id: Optional[str] = Field(default=None, max_length=128)
    reup_expires_at: Optional[datetime] = Field(default=None)
    rc_customer_id: Optional[str] = Field(default=None, max_length=128)
    bonus_analyses: int = Field(default=0)
    """Purchased / webhook bonus credits (Re-Up packs, etc.)."""
    auth_provider: Optional[str] = Field(default=None, max_length=32)
    google_sub: Optional[str] = Field(default=None, max_length=128, index=True, unique=True)
    apple_sub: Optional[str] = Field(default=None, max_length=128, index=True, unique=True)
    email_verified: bool = Field(default=False)
    bonus_analyses_granted: int = Field(default=0)
    bonus_analyses_used: int = Field(default=0)
    profile_image_url: Optional[str] = Field(default=None, max_length=400000)
    clip_retention_consent: bool = Field(default=False)
    clip_retention_consent_at: Optional[datetime] = Field(default=None)
    # Terms / privacy consent (store + GDPR Art. 7 proof via consent_events).
    consent_granted_at: Optional[datetime] = Field(default=None)
    consent_copy_version: Optional[str] = Field(default=None, max_length=32)
    consent_source: Optional[str] = Field(default=None, max_length=32)
    pending_deletion_at: Optional[datetime] = Field(default=None)
    hard_deleted_at: Optional[datetime] = Field(default=None)
    deletion_source: Optional[str] = Field(default=None, max_length=32)
    tokens_invalidated_at: Optional[datetime] = Field(default=None)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)


class ConsentEventModel(SQLModel, table=True):
    """Audit log for consent grants (proof of consent)."""

    __tablename__ = "consent_events"

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="users.id", max_length=64, index=True)
    event_type: str = Field(max_length=32)
    copy_version: str = Field(max_length=32)
    source: str = Field(max_length=32)
    occurred_at: datetime = Field(default_factory=_utcnow)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    user_agent: Optional[str] = Field(default=None, max_length=512)


class AdminRoleEventModel(SQLModel, table=True):
    """Audit log for is_admin promotions via ONFLOW_ADMIN_EMAILS bootstrap."""

    __tablename__ = "admin_role_events"

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="users.id", max_length=64, index=True)
    email: str = Field(max_length=254)
    event_type: str = Field(max_length=32)
    source: str = Field(max_length=32)
    occurred_at: datetime = Field(default_factory=_utcnow)


class SubscriptionEventModel(SQLModel, table=True):
    """Subscription and tier transition analytics events."""

    __tablename__ = "subscription_events"

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="users.id", max_length=64, index=True)
    event_type: str = Field(max_length=64)
    from_tier: Optional[str] = Field(default=None, max_length=16)
    to_tier: Optional[str] = Field(default=None, max_length=16)
    occurred_at: datetime = Field(default_factory=_utcnow)
    metadata_json: Optional[str] = Field(default=None, sa_column=Column(Text))


class SkateSessionModel(SQLModel, table=True):
    """Skating session — container for clips filmed in one outing (V1 §1.2).

    Table name is ``skate_sessions`` because ``sessions`` is reserved for auth tokens.
    """

    __tablename__ = "skate_sessions"

    id: str = Field(primary_key=True, max_length=36)
    user_id: str = Field(index=True, max_length=64)
    spot_label: Optional[str] = Field(default=None, sa_column=Column(Text))
    focus_trick: Optional[str] = Field(default=None, sa_column=Column(Text))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    started_at: datetime = Field(default_factory=_utcnow)
    ended_at: Optional[datetime] = Field(default=None)
    breakthrough_note: Optional[str] = Field(default=None, sa_column=Column(Text))
    deleted_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class SessionAttemptModel(SQLModel, table=True):
    """Client-logged session attempt (landed/missed) — canonical server store.

    Primary key is the **client-generated** id so offline outbox sync is idempotent.
    """

    __tablename__ = "session_attempts"
    __table_args__ = (
        Index("ix_session_attempts_user_session", "user_id", "session_id"),
        Index("ix_session_attempts_session_logged", "session_id", "logged_at"),
    )

    id: str = Field(primary_key=True, max_length=80)
    user_id: str = Field(index=True, max_length=64)
    session_id: str = Field(foreign_key="skate_sessions.id", max_length=36, index=True)
    trick_id: str = Field(max_length=64)
    canonical_name: str = Field(max_length=128)
    outcome: str = Field(max_length=16)  # landed | missed
    logged_at: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)
    deleted_at: Optional[datetime] = Field(default=None)


class ClipModel(SQLModel, table=True):
    """V1 clip row — two-step upload (initiate → S3 PUT → complete)."""

    __tablename__ = "clips"

    id: str = Field(primary_key=True, max_length=36)
    user_id: str = Field(index=True, max_length=64)
    session_id: Optional[str] = Field(default=None, foreign_key="skate_sessions.id", max_length=36)
    trick_id: Optional[str] = Field(default=None, max_length=64)
    storage_key: str = Field(sa_column=Column(Text))
    storage_url: str = Field(default="", sa_column=Column(Text))
    thumbnail_key: Optional[str] = Field(default=None, sa_column=Column(Text))
    thumbnail_url: Optional[str] = Field(default=None, sa_column=Column(Text))
    duration_seconds: Optional[float] = Field(default=None)
    width_px: Optional[int] = Field(default=None)
    height_px: Optional[int] = Field(default=None)
    content_type: Optional[str] = Field(default=None, max_length=64)
    size_bytes: Optional[int] = Field(default=None)
    upload_status: str = Field(default="pending", max_length=16)
    landed: Optional[bool] = Field(default=None)
    pte_rating: Optional[int] = Field(default=None)
    is_first_land: bool = Field(default=False)
    hidden_from_feed: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class FeedEventModel(SQLModel, table=True):
    """Progression feed events (V1: session_recap on session end)."""

    __tablename__ = "feed_events"
    # Defense-in-depth idempotency: at most one live event per
    # (user, source session, event type). The app layer also checks before
    # inserting; this guarantees no duplicates even under a race.
    __table_args__ = (
        Index(
            "uq_feed_events_session_event",
            "user_id",
            "skate_session_id",
            "event_type",
            unique=True,
            sqlite_where=text("deleted_at IS NULL AND skate_session_id IS NOT NULL"),
            postgresql_where=text("deleted_at IS NULL AND skate_session_id IS NOT NULL"),
        ),
    )

    id: str = Field(primary_key=True, max_length=36)
    user_id: str = Field(index=True, max_length=64)
    event_type: str = Field(max_length=24)
    event_version: str = Field(max_length=32)
    skate_session_id: Optional[str] = Field(
        default=None, foreign_key="skate_sessions.id", max_length=36
    )
    trick_id: Optional[str] = Field(default=None, max_length=64)
    clip_id: Optional[str] = Field(default=None, max_length=36)
    payload_json: str = Field(sa_column=Column(Text))
    generated_at: datetime = Field(default_factory=_utcnow)
    propagates_at: datetime = Field(default_factory=_utcnow)
    propagation_status: str = Field(default="propagated", max_length=16)
    hidden_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)


class SessionModel(SQLModel, table=True):
    """Session token -> user mapping (migrated from SQLite)."""

    __tablename__ = "sessions"

    token: str = Field(primary_key=True, max_length=128)
    user_id: str = Field(index=True, max_length=64)
    created_at: datetime = Field(default_factory=_utcnow)


class BetaFeedbackModel(SQLModel, table=True):
    """Beta tester feedback on coaching quality (migrated from SQLite)."""

    __tablename__ = "beta_feedback"

    id: str = Field(primary_key=True, default_factory=lambda: uuid.uuid4().hex[:16])
    user_id: Optional[str] = Field(default=None, index=True, max_length=64)
    job_id: Optional[str] = Field(default=None, index=True, max_length=64)
    useful: Optional[bool] = None
    accurate: Optional[bool] = None
    issue_kind: Optional[str] = Field(default=None, max_length=64)
    note: str = Field(default="", sa_column=Column(Text))
    client_kind: Optional[str] = Field(default=None, max_length=32)
    coaching_helped_next_try: Optional[bool] = None
    coaching_too_generic: Optional[bool] = None
    coaching_wrong_read: Optional[bool] = None
    best_cue_clear: Optional[bool] = None
    created_at: datetime = Field(default_factory=_utcnow)


class RcWebhookDedupModel(SQLModel, table=True):
    """RevenueCat webhook event deduplication."""

    __tablename__ = "rc_webhook_dedup"

    event_id: str = Field(primary_key=True, max_length=256)
    created_at: datetime = Field(default_factory=_utcnow)


class GeminiSpendDailyModel(SQLModel, table=True):
    """Daily Gemini spend tracker for cost-cap enforcement (UTC calendar days)."""

    __tablename__ = "gemini_spend_daily"

    spend_date: str = Field(primary_key=True, max_length=10)  # YYYY-MM-DD UTC
    spend_usd_cents: int = Field(default=0)
    job_count: int = Field(default=0)
    updated_at: datetime = Field(default_factory=_utcnow)


class ClientFunnelEventModel(SQLModel, table=True):
    """Client-originated funnel events (e.g. share flow) for admin aggregates."""

    __tablename__ = "client_funnel_events"

    id: str = Field(primary_key=True, default_factory=lambda: uuid.uuid4().hex[:20])
    user_id: str = Field(index=True, max_length=64)
    kind: str = Field(index=True, max_length=64)
    job_id: Optional[str] = Field(default=None, max_length=80)
    share_target: Optional[str] = Field(default=None, max_length=32)
    error_detail: Optional[str] = Field(default=None, sa_column=Column(Text))
    ref_source: Optional[str] = Field(default=None, max_length=32)
    created_at: datetime = Field(default_factory=_utcnow)


def tier_has_feature(tier: str, feature: str) -> bool:
    from app.core.feature_gates import tier_has_feature as _tier_has_feature

    return _tier_has_feature(tier, feature)


def get_analyses_remaining(user: UserModel) -> int:
    normalized_tier = (user.tier or "").strip().lower()
    if normalized_tier in {"trial", "pro", "session_reup"}:
        return -1
    if normalized_tier == "free_expired":
        return 0
    return max(0, int(user.bonus_analyses or 0))


def auto_downgrade_trial_users() -> None:
    from app.core.database import get_engine

    now = datetime.now(timezone.utc)
    with Session(get_engine()) as session:
        users_to_downgrade = list(
            session.exec(
                select(UserModel).where(
                    UserModel.tier == "trial",
                    UserModel.trial_expires_at.is_not(None),  # type: ignore[union-attr]
                    UserModel.trial_expires_at <= now,
                )
            )
        )
        for user in users_to_downgrade:
            user.tier = "free_expired"
            user.subscription_status = "expired"
            session.add(user)
            session.add(
                SubscriptionEventModel(
                    user_id=user.id,
                    event_type="trial_expired",
                    from_tier="trial",
                    to_tier="free_expired",
                    occurred_at=now,
                )
            )
        if users_to_downgrade:
            session.commit()
