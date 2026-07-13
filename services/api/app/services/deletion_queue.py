"""Queued hard-delete pipeline for user clip objects and clip job rows."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog

from app.repositories.clip_jobs import ClipJobRepository
from app.services.object_storage import ObjectStorage

logger = structlog.get_logger(__name__)

HARD_DELETE_TIMEOUT_SECONDS = 600


def _storage_key_from_input_reference(input_reference: str) -> str | None:
    ref = (input_reference or "").strip()
    if not ref:
        return None
    if ref.startswith("storage:"):
        key = ref.removeprefix("storage:").strip()
        return key or None
    return ref


async def enqueue_hard_delete(user_id: str, requested_at: datetime) -> None:
    """
    Enqueue hard-delete for a user.

    Redis-backed environments use ARQ. In local/dev environments without Redis,
    run synchronously in the request path: this is account deletion, so correctness
    is more important than latency and we intentionally avoid fire-and-forget.
    """
    from app.services.job_queue import get_arq_pool

    pool = await get_arq_pool()
    if pool is not None:
        await pool.enqueue_job(
            "hard_delete_user_clips",
            user_id,
            _job_id=f"hard_delete:{user_id}",
            _max_tries=3,
        )
        logger.info(
            "hard_delete_enqueued",
            user_id=user_id,
            requested_at=requested_at.isoformat(),
        )
        return

    logger.warning(
        "hard_delete_no_redis_running_sync",
        user_id=user_id,
        requested_at=requested_at.isoformat(),
    )
    await hard_delete_user_clips({}, user_id)


async def hard_delete_user_clips(ctx: dict[str, Any], user_id: str) -> dict[str, Any]:
    """ARQ worker entrypoint. Purges object storage first, then clip job rows."""
    del ctx

    async def _run() -> dict[str, Any]:
        from sqlmodel import Session

        from app.core.database import create_db_tables, get_engine
        from app.repositories.clip_jobs import SqlClipJobRepository
        from app.services.object_storage import build_storage

        create_db_tables()
        engine = get_engine()
        repo = SqlClipJobRepository(lambda: Session(engine))
        storage = build_storage()
        return await _hard_delete_user_clips_impl(user_id, repo, storage)

    return await asyncio.wait_for(_run(), timeout=HARD_DELETE_TIMEOUT_SECONDS)


async def _hard_delete_user_clips_impl(
    user_id: str,
    repo: ClipJobRepository,
    storage: ObjectStorage,
) -> dict[str, Any]:
    refs = repo.list_storage_refs_for_user(user_id)
    by_key: dict[str, list[str]] = {}
    job_ids_without_storage: list[str] = []

    for job_id, input_reference in refs:
        key = _storage_key_from_input_reference(input_reference)
        if key is None:
            job_ids_without_storage.append(job_id)
            logger.warning(
                "hard_delete_clip_missing_storage_key",
                user_id=user_id,
                job_id=job_id,
                input_reference=input_reference,
            )
            continue
        by_key.setdefault(key, []).append(job_id)

    clip_count = len(refs)
    success_job_ids: list[str] = list(job_ids_without_storage)
    failed_keys: list[str] = []

    logger.info(
        "hard_delete_started",
        user_id=user_id,
        clip_count=clip_count,
        object_count=len(by_key),
    )

    for key, job_ids in by_key.items():
        try:
            await storage.delete(key)
        except Exception as exc:
            failed_keys.append(key)
            logger.warning(
                "hard_delete_storage_delete_failed",
                user_id=user_id,
                key=key,
                job_ids=job_ids,
                error=str(exc),
                exc_info=True,
            )
            continue
        success_job_ids.extend(job_ids)

    if success_job_ids:
        try:
            repo.delete_jobs_by_ids(success_job_ids)
        except Exception:
            logger.exception(
                "hard_delete_db_delete_failed",
                user_id=user_id,
                job_ids=success_job_ids,
            )
            raise

    success_count = len(success_job_ids)
    failure_count = len(failed_keys)
    report = {
        "user_id": user_id,
        "clip_count": clip_count,
        "object_count": len(by_key),
        "success_count": success_count,
        "failure_count": failure_count,
        "failed_keys": failed_keys,
    }
    logger.info("hard_delete_complete", **report)
    return report
