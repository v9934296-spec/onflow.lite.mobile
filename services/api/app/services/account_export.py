"""Assemble a complete account data export (GDPR/CCPA completeness)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.core.database import get_engine
from app.models import (
    CustomLineModel,
    FeedEventModel,
    LineAttemptModel,
    MilestoneModel,
    SessionAttemptModel,
    SkateSessionModel,
    TrickStatModel,
)
from app.repositories.clip_jobs import ClipJobRepository
from app.repositories.identity import IdentityRepository
from app.routers.consent import consent_status_from_user


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def build_account_export(
    user_id: str,
    *,
    identity: IdentityRepository,
    repo: ClipJobRepository,
) -> dict[str, Any]:
    u = identity.get_user(user_id)
    if u is None:
        raise LookupError("user not found")

    jobs: list[dict[str, Any]] = [
        {
            "job_id": rec.id,
            "status": rec.status,
            "clip_label": rec.clip_label,
            "created_at": _iso(rec.created_at),
            "failure_reason": rec.failure_reason,
            "result": rec.result_json,
            "clip_metadata": rec.clip_metadata,
            "quota_source": rec.quota_source,
        }
        for rec in repo.iter_all_for_user(user_id)
    ]

    sessions: list[dict[str, Any]] = []
    session_attempts: list[dict[str, Any]] = []
    feed_events: list[dict[str, Any]] = []
    trick_stats: list[dict[str, Any]] = []
    milestones: list[dict[str, Any]] = []
    custom_lines: list[dict[str, Any]] = []
    line_attempts: list[dict[str, Any]] = []

    with Session(get_engine()) as session:
        for row in session.exec(
            select(SkateSessionModel)
            .where(SkateSessionModel.user_id == user_id)
            .order_by(SkateSessionModel.started_at.desc())
        ):
            sessions.append(
                {
                    "id": row.id,
                    "spot_label": row.spot_label,
                    "focus_trick": row.focus_trick,
                    "notes": row.notes,
                    "started_at": _iso(row.started_at),
                    "ended_at": _iso(row.ended_at),
                    "breakthrough_note": row.breakthrough_note,
                    "deleted_at": _iso(row.deleted_at),
                    "created_at": _iso(row.created_at),
                }
            )

        for row in session.exec(
            select(SessionAttemptModel)
            .where(
                SessionAttemptModel.user_id == user_id,
                SessionAttemptModel.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            .order_by(SessionAttemptModel.logged_at.desc())
        ):
            session_attempts.append(
                {
                    "id": row.id,
                    "session_id": row.session_id,
                    "trick_id": row.trick_id,
                    "canonical_name": row.canonical_name,
                    "outcome": row.outcome,
                    "logged_at": _iso(row.logged_at),
                }
            )

        for row in session.exec(
            select(FeedEventModel)
            .where(FeedEventModel.user_id == user_id)
            .order_by(FeedEventModel.generated_at.desc())
        ):
            feed_events.append(
                {
                    "id": row.id,
                    "event_type": row.event_type,
                    "event_version": row.event_version,
                    "skate_session_id": row.skate_session_id,
                    "payload_json": row.payload_json,
                    "generated_at": _iso(row.generated_at),
                    "propagation_status": row.propagation_status,
                    "deleted_at": _iso(row.deleted_at),
                }
            )

        for row in session.exec(
            select(TrickStatModel)
            .where(TrickStatModel.user_id == user_id)
            .order_by(TrickStatModel.created_at.desc())
        ):
            trick_stats.append(
                {
                    "id": row.id,
                    "job_id": row.job_id,
                    "trick_name": row.trick_name,
                    "stance": row.stance,
                    "obstacle": row.obstacle,
                    "landed": row.landed,
                    "review_readiness": row.review_readiness,
                    "created_at": _iso(row.created_at),
                    "session_id": row.session_id,
                    "land_score": row.land_score,
                }
            )

        for row in session.exec(
            select(MilestoneModel)
            .where(MilestoneModel.user_id == user_id)
            .order_by(MilestoneModel.achieved_at.desc())
        ):
            milestones.append(
                {
                    "id": row.id,
                    "milestone_key": row.milestone_key,
                    "trick_name": row.trick_name,
                    "session_id": row.session_id,
                    "job_id": row.job_id,
                    "achieved_at": _iso(row.achieved_at),
                }
            )

        for row in session.exec(
            select(CustomLineModel)
            .where(CustomLineModel.user_id == user_id)
            .order_by(CustomLineModel.created_at.desc())
        ):
            custom_lines.append(
                {
                    "id": row.id,
                    "line_name": row.line_name,
                    "trick_sequence": row.trick_sequence,
                    "created_at": _iso(row.created_at),
                    "updated_at": _iso(row.updated_at),
                }
            )

        for row in session.exec(
            select(LineAttemptModel)
            .where(LineAttemptModel.user_id == user_id)
            .order_by(LineAttemptModel.created_at.desc())
        ):
            line_attempts.append(
                {
                    "id": row.id,
                    "line_id": row.line_id,
                    "job_id": row.job_id,
                    "landed": row.landed,
                    "session_id": row.session_id,
                    "created_at": _iso(row.created_at),
                }
            )

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "user": {
            "id": u.id,
            "email": u.email,
            "tier": u.tier,
            "subscription_status": u.subscription_status,
            "trial_expires_at": _iso(u.trial_expires_at),
            "bonus_analyses": identity.get_bonus_analyses(user_id),
            "clip_retention_consent": bool(u.clip_retention_consent),
            "created_at": _iso(u.created_at),
        },
        "consent": consent_status_from_user(u).model_dump(),
        "clips": jobs,
        "sessions": sessions,
        "session_attempts": session_attempts,
        "feed_events": feed_events,
        "trick_stats": trick_stats,
        "milestones": milestones,
        "custom_lines": custom_lines,
        "line_attempts": line_attempts,
        "consent_events": identity.list_consent_events(user_id),
        "export_generated_at": generated_at,
        "policy_version_at_export": "v1_2026_04_14",
    }
