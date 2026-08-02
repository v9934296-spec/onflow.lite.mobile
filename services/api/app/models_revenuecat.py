"""RevenueCat-specific persistence models.

Kept separate from the main model module so webhook delivery state remains an
explicit billing concern rather than another field cluster on ``users``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RcEntitlementStateModel(SQLModel, table=True):
    """Per-product RevenueCat entitlement state for one OnFlow user.

    The JSON object is keyed by Store product id. Each entry stores whether that
    product is currently active plus the RevenueCat event timestamp and event id
    that established the state. Keeping all products under one user-owned row
    lets the webhook lock once, order each product independently, and preserve Pro
    while any configured Pro product remains active.
    """

    __tablename__ = "rc_entitlement_state"

    user_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    product_states_json: str = Field(
        default="{}",
        sa_column=Column(Text, nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
