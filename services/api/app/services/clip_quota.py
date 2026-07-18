"""Clip submission quota: Pro unlimited → bonus pool → monthly free cap."""

from __future__ import annotations

import threading
from collections.abc import Callable

from fastapi import HTTPException, Request

from app.core.config import get_settings
from app.core.tiers import normalize_tier, tier_has_unlimited_analyses
from app.domain.clip_job import ClipJobRecord, JobAlreadyExists
from app.repositories.clip_jobs import ClipJobRepository
from app.repositories.identity import IdentityRepository

# Process-local serialization for free-tier quota decisions. Prevents concurrent
# complete-upload on the same API process from double-spending monthly free.
# Multi-worker fleets still need a distributed lock / ledger for hard caps.
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
    quota_source: 'unlimited' | 'bonus' | 'monthly' | None (should not happen).

    Order: unlimited tier → monthly free cap → OAuth signup bonus pool → purchased bonus pool.

    Prefer ``create_job_charging_quota`` when inserting the job so count + create
    share the same per-user lock.
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


def create_job_charging_quota(
    request: Request,
    user_id: str,
    build_record: Callable[[str, str | None], ClipJobRecord],
) -> ClipJobRecord:
    """
    Choose quota source and insert the job under a per-user lock.

    Serializes concurrent complete-upload for the same user within one API
    process so monthly free cannot be over-served by a TOCTOU race. Same-clip
    concurrent completes raise ``JobAlreadyExists`` (caller treats as idempotent).
    """
    settings = get_settings()
    db: IdentityRepository = request.app.state.db
    repo: ClipJobRepository = request.app.state.repo

    with _lock_for_user(user_id):
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
