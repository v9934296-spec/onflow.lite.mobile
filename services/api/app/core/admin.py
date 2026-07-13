"""Admin role bootstrap: ONFLOW_ADMIN_EMAILS -> users.is_admin on verified sign-in."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.models import AdminRoleEventModel, UserModel

if TYPE_CHECKING:
    from sqlmodel import Session

logger = logging.getLogger(__name__)

# Practical RFC5322 subset: local@domain.tld (allows .test for unit tests).
_ADMIN_EMAIL_RE = re.compile(
    r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,63}$",
    re.IGNORECASE,
)


def parse_admin_emails_strict(raw: str) -> set[str]:
    """
    Parse ONFLOW_ADMIN_EMAILS into a normalized set.

    Raises ValueError when the list is malformed (empty entries, invalid format,
    duplicates).
    """
    text = (raw or "").strip()
    if not text:
        return set()
    parts = [segment.strip() for segment in text.split(",")]
    if any(not segment for segment in parts):
        raise ValueError(
            "ONFLOW_ADMIN_EMAILS must be a comma-separated list with no empty entries."
        )
    normalized: list[str] = []
    for part in parts:
        email = part.strip().lower()
        if len(email) > 254:
            raise ValueError(f"ONFLOW_ADMIN_EMAILS entry too long: {part!r}")
        if not _ADMIN_EMAIL_RE.fullmatch(email):
            raise ValueError(f"ONFLOW_ADMIN_EMAILS contains invalid email: {part!r}")
        normalized.append(email)
    if len(normalized) != len(set(normalized)):
        raise ValueError("ONFLOW_ADMIN_EMAILS contains duplicate emails.")
    return set(normalized)


def configured_admin_emails() -> set[str]:
    """Parse ONFLOW_ADMIN_EMAILS into a set of lowercase emails."""
    return parse_admin_emails_strict(get_settings().admin_emails or "")


def email_grants_admin(email: str | None) -> bool:
    norm = (email or "").strip().lower()
    return bool(norm) and norm in configured_admin_emails()


def _record_admin_promotion(
    *,
    user: UserModel,
    source: str,
    session: Session | None,
) -> None:
    logger.warning(
        "admin_role_promoted user_id=%s email=%s source=%s",
        user.id,
        user.email,
        source,
    )
    if session is None:
        return
    session.add(
        AdminRoleEventModel(
            user_id=user.id,
            email=(user.email or "").strip().lower()[:254],
            source=source[:32],
            event_type="promoted",
        )
    )


def promote_admin_if_eligible(
    user: UserModel,
    *,
    source: str,
    session: Session | None = None,
) -> bool:
    """
    Promote user to admin when their verified email is in ONFLOW_ADMIN_EMAILS.

    Returns True when is_admin was set. Writes structured logs and an audit row
    when session is provided.
    """
    if user.is_admin:
        return False
    if not user.email_verified:
        return False
    if not email_grants_admin(user.email):
        return False
    user.is_admin = True
    _record_admin_promotion(user=user, source=source, session=session)
    return True


def sync_admin_role_for_email(
    user: UserModel,
    *,
    source: str = "legacy",
    session: Session | None = None,
) -> bool:
    """Backward-compatible alias for promote_admin_if_eligible."""
    return promote_admin_if_eligible(user, source=source, session=session)
