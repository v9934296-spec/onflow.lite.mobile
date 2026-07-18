from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sqlmodel import Session

from app.core.config import get_settings
from app.core.database import create_db_tables, get_engine
from app.core.logging import RequestIdMiddleware, setup_logging

setup_logging()

from app.repositories.clip_jobs import ClipJobRepository, SqlClipJobRepository
from app.repositories.identity import IdentityRepository
from app.routers import (
    account,
    admin_share,
    auth,
    beta_events,
    billing_sync,
    clips,
    clips_v1,
    consent,
    feed,
    health,
    lines,
    oauth_signin,
    progression,
    session_attempts,
    sessions,
    stats,
    webhooks,
)
logger = structlog.get_logger(__name__)
logging.getLogger("onflow.beta").setLevel(logging.INFO)

_settings = get_settings()
if (_settings.sentry_dsn or "").strip():
    # Release tag — prefer the Railway commit SHA when available so Sentry can
    # group issues by deploy. Falls back to "local" in dev. Anything else can
    # be overridden via ONFLOW_SENTRY_RELEASE.
    _sentry_release = (
        os.getenv("ONFLOW_SENTRY_RELEASE")
        or os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("RAILWAY_GIT_COMMIT_SHORT_SHA")
        or "local"
    )
    sentry_sdk.init(
        dsn=_settings.sentry_dsn,
        environment=_settings.sentry_environment,
        release=_sentry_release,
        traces_sample_rate=_settings.sentry_traces_sample_rate,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        send_default_pii=False,
    )


async def _resume_interrupted_jobs(app: FastAPI) -> None:
    """Re-queue pending/processing jobs after API restart via ARQ (or in-process fallback)."""
    from datetime import datetime, timezone

    repo: ClipJobRepository = app.state.repo
    storage = app.state.storage
    from app.services.job_queue import enqueue_clip_job

    RESUME_SKIP_RECENT_SECONDS = 60  # skip jobs updated in the last 60s — ARQ likely still has them
    now = datetime.now(timezone.utc)

    resumable = list(repo.list_resumable())
    logger.info("startup: found %d resumable jobs", len(resumable))
    try:
        import sentry_sdk

        sentry_sdk.set_measurement("startup_resumable_queue_depth", len(resumable), "none")
    except Exception:
        pass

    for job in resumable:
        updated = job.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age_seconds = (now - updated).total_seconds()
        if age_seconds < RESUME_SKIP_RECENT_SECONDS:
            logger.info(
                "resume: skipping recent job (age=%.0fs) job_id=%s", age_seconds, job.id
            )
            continue
        ref = job.input_reference

        if ref.startswith("storage:"):
            storage_key = ref.split(":", 1)[1]
            try:
                if not await storage.exists(storage_key):
                    rec = repo.get(job.id)
                    if rec and rec.status in ("pending", "processing"):
                        rec.with_status("failed", failure_reason="upload_missing")
                        repo.update(rec)
                    logger.warning("resume: storage key missing job_id=%s", job.id)
                    continue
                await enqueue_clip_job(
                    job.id,
                    storage_key,
                    job.user_id,
                    fallback_repo=repo,
                    fallback_storage=storage,
                )
                logger.info("resume: re-enqueued job_id=%s", job.id)
            except Exception:
                logger.exception("resume: failed to enqueue job_id=%s", job.id)
        else:
            # Legacy local upload — mark failed
            rec = repo.get(job.id)
            if rec and rec.status in ("pending", "processing"):
                rec.with_status("failed", failure_reason="upload_missing")
                repo.update(rec)
            logger.warning("resume: legacy ref gone job_id=%s ref=%s", job.id, ref)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    settings.retention_dir_resolved.mkdir(parents=True, exist_ok=True)

    create_db_tables()
    engine = get_engine()
    session_factory = lambda: Session(engine)
    app.state.repo = SqlClipJobRepository(session_factory)
    db = IdentityRepository(session_factory)
    db.init_schema()
    app.state.db = db

    app.state.upload_dir = upload_dir
    from app.services.object_storage import build_storage
    app.state.storage = build_storage()
    app.state.settings = settings

    from app.services.feed_sse_hub import get_feed_sse_hub

    app.state.feed_sse_hub = get_feed_sse_hub()

    from app.core.rate_limit import validate_rate_limit_storage_at_startup

    validate_rate_limit_storage_at_startup()

    # Async Redis client for idempotency cache + Gemini result cache.
    # Best-effort — skipped (None) when ONFLOW_REDIS_URL is not configured or unreachable.
    redis_url = (settings.redis_url or "").strip()
    if redis_url:
        try:
            import redis.asyncio as aioredis  # type: ignore[import]

            app.state.redis = aioredis.from_url(
                redis_url, decode_responses=True, socket_timeout=1.0
            )
            logger.info("async_redis_ready", url_set=True)
        except Exception as exc:
            logger.warning(
                "async_redis_unavailable",
                error=str(exc),
                hint="idempotency + Gemini cache disabled",
            )
            app.state.redis = None
    else:
        app.state.redis = None

    db_kind = "postgres" if settings.get_database_url().startswith("postgresql") else "sqlite"
    logger.info(
        "API ready; db=%s uploads=%s",
        db_kind,
        upload_dir.resolve(),
    )
    await _resume_interrupted_jobs(app)

    # Best-effort cleanup of abandoned pending uploads (storage + clip rows).
    try:
        from app.services.clip_pending_reaper import reap_abandoned_pending_clips

        report = await reap_abandoned_pending_clips(storage=app.state.storage)
        logger.info("startup_pending_reaper", **report)
    except Exception:
        logger.exception("startup_pending_reaper_failed")

    yield


def create_app() -> FastAPI:
    get_settings.cache_clear()
    settings = get_settings()
    app = FastAPI(title="OnFlow API", lifespan=lifespan)

    if os.environ.get("PYTEST_CURRENT_TEST"):
        @app.middleware("http")
        async def _refresh_settings_cache_for_pytest(request, call_next):
            get_settings.cache_clear()
            return await call_next(request)

    _raw_origins = (settings.cors_origins or "").strip()
    if _raw_origins == "*":
        origins = ["*"]
    elif _raw_origins:
        origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    else:
        # No origins configured — allow localhost only (safe default for dev; set ONFLOW_CORS_ORIGINS in prod)
        origins = ["http://localhost:8081", "http://localhost:3000", "http://127.0.0.1:8081"]
        if settings.is_production:
            logger.warning(
                "ONFLOW_CORS_ORIGINS is not set in production — CORS is restricted to localhost only. "
                "Set ONFLOW_CORS_ORIGINS to your app domain."
            )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response

    from app.core.rate_limit import limiter

    def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
        response = JSONResponse(
            {"error": f"Rate limit exceeded: {exc.detail}"},
            status_code=429,
        )
        response.headers["Retry-After"] = str(24 * 3600)
        return response

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": "OnFlow API",
            "status": "running",
            "health": "/health",
            "docs": "/docs",
        }

    app.include_router(health.router)
    app.include_router(account.router)
    app.include_router(consent.router)
    app.include_router(auth.router)
    app.include_router(oauth_signin.router)
    app.include_router(beta_events.router)
    app.include_router(admin_share.router)
    app.include_router(clips.router)
    app.include_router(clips_v1.router)
    app.include_router(sessions.router)
    app.include_router(session_attempts.router)
    app.include_router(feed.router)
    app.include_router(progression.router)
    app.include_router(stats.router)
    app.include_router(lines.router)
    app.include_router(billing_sync.router)
    app.include_router(webhooks.router)
    return app


app = create_app()
