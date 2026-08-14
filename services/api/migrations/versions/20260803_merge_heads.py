"""Merge heads: clip job leases + RevenueCat entitlement state.

20260801_clip_job_leases and 20260802_rc_entitlement_state both branched off
20260717_session_attempts independently, leaving two Alembic heads. They touch
unrelated tables (clip_jobs vs. rc_entitlement_state), so this merge carries no
schema change of its own — it only reunites the graph into a single head.

Revision ID: 20260803_merge_heads
Revises: 20260801_clip_job_leases, 20260802_rc_entitlement_state
Create Date: 2026-08-03
"""

from __future__ import annotations

revision = "20260803_merge_heads"
down_revision = ("20260801_clip_job_leases", "20260802_rc_entitlement_state")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
