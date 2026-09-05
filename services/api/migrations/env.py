"""Alembic environment — SQLModel metadata from application models."""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Import ALL models so their tables are registered on metadata. If a table
# model is missing here, ``alembic revision --autogenerate`` sees the table in
# the database but not in metadata and emits DROP TABLE for it. Keep this list
# in sync with app.core.database.create_db_tables.
from app.models import (  # noqa: F401
    BetaFeedbackModel,
    ClientFunnelEventModel,
    ClipJobModel,
    ClipModel,
    ConsentEventModel,
    CustomLineModel,
    FeedEventModel,
    GeminiSpendDailyModel,
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
from app.models_revenuecat import RcEntitlementStateModel  # noqa: F401

try:
    from migrations.alembic_version_width import ensure_alembic_version_num_width
except ImportError:  # Alembic may put only script_location on sys.path
    from alembic_version_width import ensure_alembic_version_num_width

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def get_url() -> str:
    return os.environ.get("ONFLOW_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""


def run_migrations_offline() -> None:
    url = get_url()
    if not url:
        raise RuntimeError("Set ONFLOW_DATABASE_URL or DATABASE_URL for Alembic migrations.")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_url()
    if not url:
        raise RuntimeError("Set ONFLOW_DATABASE_URL or DATABASE_URL for Alembic migrations.")
    connectable = engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Widen/create version_num before Alembic writes a revision id.
        # Production is VARCHAR(32); 20260804_attempt_sync_immutability is 34.
        ensure_alembic_version_num_width(connection)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
