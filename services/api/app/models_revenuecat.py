"""RevenueCat-specific persistence models.

Kept separate from the main model module so webhook delivery state remains an
explicit billing concern rather than another field cluster on ``users``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RcEntitlementStateModel(SQLModel, table=True):
    """Latest entitlement mutation applied for one OnFlow user.

    RevenueCat delivers webhooks at least once and network delivery can be out of
    order. This row is locked together with the user row so an older expiration
    cannot overwrite a newer purchase or renewal.
    """

    __tablename__ = "rc_entitlement_state"

    user_id: str = Field(primary_key=True, max_length=64)
    last_event_timestamp_ms: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, nullable=True),
    )
    last_event_id: Optional[str] = Field(default=None, max_length=256)
    last_tier: Optional[str] = Field(default=None, max_length=16)
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
