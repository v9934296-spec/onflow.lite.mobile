"""Database engine, session factory, and table creation for clip jobs."""
from __future__ import annotations

import logging

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

_log = logging.getLogger(__name__)

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.get_database_url()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        pool_kwargs: dict = {}
        if not url.startswith("sqlite"):
            # Postgres pool tuning (env-driven so Railway can match its plan limits).
            pool_kwargs = {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_recycle": settings.db_pool_recycle,
                "pool_pre_ping": True,
            }
        else:
            pool_kwargs = {"pool_pre_ping": True}
        _engine = create_engine(url, connect_args=connect_args, **pool_kwargs)
    return _engine


def dispose_engine() -> None:
    """Dispose the process-scoped SQLAlchemy engine (API lifespan shutdown)."""
    global _engine
    eng = _engine
    _engine = None
    if eng is not None:
        eng.dispose()


def create_db_tables() -> None:
    """
    Create SQLModel tables for local bootstrap (empty SQLite / first run).

    **Schema migrations:** use Alembic only — ``alembic upgrade head`` from ``services/api``.
    Skipped in production/staging so missing migrations cannot be masked by create_all.
    """
    settings = get_settings()
    if settings.is_production_or_staging:
        _log.info(
            "create_db_tables skipped (Alembic owns schema in env=%s)",
            settings.env,
        )
        return

    from app.models import (  # noqa: F401 — registers tables
        BetaFeedbackModel,
        ClientFunnelEventModel,
        ClipJobModel,
        ClipModel,
        GeminiSpendDailyModel,
        ConsentEventModel,
        CustomLineModel,
        FeedEventModel,
        LineAttemptModel,
        MilestoneModel,
        RcWebhookDedupModel,
        SessionAttemptModel,
        SessionModel,
        SkateSessionModel,
        SubscriptionEventModel,
        TrickStatModel,
        UserModel,
    )

    SQLModel.metadata.create_all(get_engine())
    _log.debug("create_db_tables: SQLModel.metadata.create_all completed")


def get_db():
    """FastAPI dependency: yields a SQLModel Session."""
    with Session(get_engine()) as session:
        yield session
