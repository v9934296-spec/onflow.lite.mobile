"""Clip submission quota: Pro unlimited → bonus pool → monthly free cap.

Cross-replica safety: ``create_job_charging_quota`` uses a single Postgres/SQLite
transaction with ``SELECT … FOR UPDATE`` on the user row, then counts monthly
jobs and inserts the clip job in the same transaction. Process-local locks remain
as a fast path within one API worker.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from fastapi import HTTPException, Request
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_engine
from app.core.tiers import normalize_tier, tier_has_unlimited_analyses
from app.domain.clip_job import ClipJobRecord, JobAlreadyExists
from app.models import ClipJobModel, UserModel
from app.repositories.clip_jobs import ClipJobRepository, _current_month_bounds_utc
from app.repositories.identity import IdentityRepository

_user_locks: dict[str, threading.Lock] = {}
_user_locks_guard = threading.Lock()


def _lock_for_user(user_id: str) -> threading.Lock:
    with _user_locks_guard:
        lock = _user_locks.get(user_id)
        if lock is None:
            lock = threading.Lock()
            _user_locks[user_id] = lock
        return lock


def reserve_clip_submission(request: Request, user_id: str) -> tuple[str, str | None]:
    """
    Decide how this submission is charged. Returns (tier_for_job, quota_source).

    Prefer ``create_job_charging_quota`` when inserting the job so count + create
    share the same lock / transaction.
    """
    settings = get_settings()
    db: IdentityRepository = request.app.state.db
    repo: ClipJobRepository = request.app.state.repo

    with _lock_for_user(user_id):
        return _decide_quota(db, repo, user_id, settings.rate_limit_free)


def _decide_quota(
    db: IdentityRepository,
    repo: ClipJobRepository,
    user_id: str,
    rate_limit_free: int,
) -> tuple[str, str | None]:
    tier = normalize_tier(db.get_user_tier(user_id))
    if tier_has_unlimited_analyses(tier):
        return tier, "unlimited"

    cap = max(1, rate_limit_free)
    used = repo.count_monthly_free_jobs(user_id)
    if used < cap:
        return tier, "monthly"

    if db.try_consume_one_bonus(user_id):
        return tier, "bonus"

    raise HTTPException(
        status_code=429,
        detail=(
            "Monthly free analysis limit reached. Upgrade, purchase a Re-Up Pack, "
            "or wait until next month."
        ),
    )


def _consume_bonus_on_row(row: UserModel) -> bool:
    granted = row.bonus_analyses_granted or 0
    used = row.bonus_analyses_used or 0
    if granted > used:
        row.bonus_analyses_used = used + 1
        return True
    if (row.bonus_analyses or 0) > 0:
        row.bonus_analyses = (row.bonus_analyses or 0) - 1
        return True
    return False


def _record_to_model(record: ClipJobRecord) -> ClipJobModel:
    m = ClipJobModel(
        id=record.id,
        user_id=record.user_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        input_reference=record.input_reference,
        failure_reason=record.failure_reason,
        clip_label=record.clip_label,
        tier=record.tier,
        quota_source=record.quota_source,
        claim_token=record.claim_token,
        claimed_at=record.claimed_at,
        lease_expires_at=record.lease_expires_at,
        attempt_number=int(record.attempt_number or 0),
    )
    m.result_json = record.result_json
    m.clip_metadata = record.clip_metadata
    return m


def _count_monthly_free_jobs(session: Session, user_id: str) -> int:
    month_start, next_month_start = _current_month_bounds_utc()
    return int(
        session.exec(
            select(func.count())
            .select_from(ClipJobModel)
            .where(
                ClipJobModel.user_id == user_id,
                ClipJobModel.created_at >= month_start,
                ClipJobModel.created_at < next_month_start,
                or_(
                    ClipJobModel.quota_source.is_(None),
                    ClipJobModel.quota_source == "monthly",
                ),
            )
        ).one()
    )


def _quota_exhausted_http() -> HTTPException:
    return HTTPException(
        status_code=429,
        detail=(
            "Monthly free analysis limit reached. Upgrade, purchase a Re-Up Pack, "
            "or wait until next month."
        ),
    )


def _create_job_charging_quota_sql(
    db: IdentityRepository,
    user_id: str,
    build_record: Callable[[str, str | None], ClipJobRecord],
    rate_limit_free: int,
) -> ClipJobRecord:
    """Single-transaction charge: lock user, count monthly, insert job."""
    with Session(get_engine()) as session:
        row = session.exec(
            select(UserModel).where(UserModel.id == user_id).with_for_update()
        ).first()
        cap = max(1, rate_limit_free)

        if row is None:
            # Dev Bearer / missing identity row: free monthly only (matches get_user_tier).
            tier = "free"
            if _count_monthly_free_jobs(session, user_id) >= cap:
                raise _quota_exhausted_http()
            quota_src: str | None = "monthly"
        else:
            db._expire_trial_if_due(session, row)
            tier = normalize_tier(row.tier)
            if tier_has_unlimited_analyses(tier):
                quota_src = "unlimited"
            elif _count_monthly_free_jobs(session, user_id) < cap:
                quota_src = "monthly"
            elif _consume_bonus_on_row(row):
                session.add(row)
                quota_src = "bonus"
            else:
                raise _quota_exhausted_http()

        record = build_record(tier, quota_src)
        try:
            session.add(_record_to_model(record))
            session.commit()
        except IntegrityError:
            # Bonus decrement (if any) was in this same transaction — rollback
            # already restores it. Do not call refund_one_bonus here.
            session.rollback()
            raise JobAlreadyExists(record.id)
        return record


def create_job_charging_quota(
    request: Request,
    user_id: str,
    build_record: Callable[[str, str | None], ClipJobRecord],
) -> ClipJobRecord:
    """
    Choose quota source and insert the job under a per-user lock.

    On SQL backends, charge + insert run in one ``FOR UPDATE`` transaction so
    multi-replica APIs cannot over-serve free/bonus quota.
    """
    settings = get_settings()
    db: IdentityRepository = request.app.state.db
    repo: ClipJobRepository = request.app.state.repo

    with _lock_for_user(user_id):
        from app.repositories.clip_jobs import SqlClipJobRepository

        if isinstance(repo, SqlClipJobRepository):
            return _create_job_charging_quota_sql(
                db, user_id, build_record, settings.rate_limit_free
            )

        tier, quota_src = _decide_quota(db, repo, user_id, settings.rate_limit_free)
        record = build_record(tier, quota_src)
        try:
            _create_exclusive(repo, record)
        except JobAlreadyExists:
            if quota_src == "bonus":
                db.refund_one_bonus(user_id)
            raise
        return record


def _create_exclusive(repo: ClipJobRepository, record: ClipJobRecord) -> None:
    create_ex = getattr(repo, "create_exclusive", None)
    if callable(create_ex):
        create_ex(record)
        return
    if repo.get(record.id) is not None:
        raise JobAlreadyExists(record.id)
    repo.create(record)
