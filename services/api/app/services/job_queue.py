"""ARQ job queue for clip processing. Falls back to asyncio.create_task when Redis is not configured."""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.config import get_settings
from app.services.deletion_queue import hard_delete_user_clips

logger = structlog.get_logger(__name__)

_arq_pool = None


async def get_arq_pool():
    """Lazy-init ARQ Redis pool."""
    global _arq_pool
    if _arq_pool is not None:
        return _arq_pool
    settings = get_settings()
    if not settings.redis_url:
        return None
    from arq import create_pool
    from arq.connections import RedisSettings

    _arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _arq_pool


async def enqueue_clip_job(
    job_id: str,
    storage_key: str,
    user_id: str,
    *,
    fallback_repo=None,
    fallback_storage=None,
) -> None:
    """
    Enqueue a clip processing job. Uses ARQ if Redis is configured,
    otherwise falls back to asyncio.create_task (dev mode).
    """
    pool = await get_arq_pool()

    if pool is not None:
        await pool.enqueue_job(
            "process_clip_job",
            job_id,
            storage_key,
            user_id,
            _job_id=f"clip:{job_id}",
        )
        logger.info("enqueued_to_arq job_id=%s storage_key=%s", job_id, storage_key)
        return

    # No Redis pool. Config validation already requires ONFLOW_REDIS_URL in
    # production/staging, but fail closed here too: never run heavy clip analysis
    # in-process inside the API event loop in production (mirrors the
    # get_database_url() production guard). The in-process path is dev-only.
    if get_settings().is_production:
        raise RuntimeError(
            "ONFLOW_REDIS_URL is required in production; refusing to run clip "
            "analysis in-process inside the API event loop."
        )

    logger.warning("no_redis: running clip job in-process job_id=%s", job_id)
    from app.services.clip_worker import run_clip_job

    async def _run() -> None:
        if fallback_storage:
            file_path = await fallback_storage.get_path(storage_key)
        else:
            from app.services.object_storage import build_storage
            file_path = await build_storage().get_path(storage_key)
        await run_clip_job(
            job_id, file_path, fallback_repo, user_id=user_id, storage_key=storage_key
        )

    asyncio.create_task(_run())


async def process_clip_job(ctx: dict[str, Any], job_id: str, storage_key: str, user_id: str) -> str:
    """
    ARQ worker function. This runs in the worker process, not in the API process.
    Must be idempotent: if called twice for the same job_id, the second call is a no-op.
    """
    del ctx
    from sqlmodel import Session

    from app.core.database import create_db_tables, get_engine
    from app.repositories.clip_jobs import SqlClipJobRepository
    from app.services.clip_worker import run_clip_job
    from app.services.object_storage import build_storage

    create_db_tables()
    engine = get_engine()
    repo = SqlClipJobRepository(lambda: Session(engine))
    storage = build_storage()

    existing = repo.get(job_id)
    if existing and existing.status in ("completed", "failed"):
        logger.info("idempotent_skip job_id=%s status=%s", job_id, existing.status)
        return f"skipped:{existing.status}"

    file_path = await storage.get_path(storage_key)
    await run_clip_job(job_id, file_path, repo, user_id=user_id, storage_key=storage_key)
    return f"done:{job_id}"


def _worker_max_jobs() -> int:
    try:
        return max(1, int(get_settings().arq_max_jobs))
    except Exception:
        return 10


def _worker_job_timeout() -> int:
    try:
        return max(1, int(get_settings().arq_job_timeout))
    except Exception:
        return 300


class WorkerSettings:
    """ARQ worker settings. Run with: arq app.services.job_queue.WorkerSettings

    ``max_jobs`` and ``job_timeout`` are sourced from Settings so Railway can tune
    horizontal scale (ONFLOW_ARQ_MAX_JOBS, ONFLOW_ARQ_JOB_TIMEOUT) without code
    changes. ARQ reads these as class attributes, so resolve them at import time.
    """

    functions = [process_clip_job, hard_delete_user_clips]
    max_jobs = _worker_max_jobs()
    job_timeout = _worker_job_timeout()
    max_tries = 2
    retry_delay = 5

    @property
    def redis_settings(self):
        from arq.connections import RedisSettings

        settings = get_settings()
        if not settings.redis_url:
            raise RuntimeError("ONFLOW_REDIS_URL must be set for the ARQ worker.")
        return RedisSettings.from_dsn(settings.redis_url)
