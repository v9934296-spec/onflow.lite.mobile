"""Admin-only route dependency (Bearer auth + users.is_admin)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.core.auth import get_current_user


def require_admin(
    request: Request,
    user_id: str = Depends(get_current_user),
) -> str:
    """Authenticated user whose users.is_admin flag is set. 403 otherwise."""
    user = request.app.state.db.get_user(user_id)
    if user is None or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user_id
