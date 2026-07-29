"""Push feed SSE events after DB writes (Step 10)."""
from __future__ import annotations

import logging

from sqlmodel import Session

from app.models import FeedEventModel
from app.services.feed_sse_hub import get_feed_sse_hub

logger = logging.getLogger(__name__)


def notify_feed_event_created(db: Session, event: FeedEventModel) -> None:
    """Emit ``feed_event`` over SSE when a propagated event is committed."""
    if event.propagation_status != "propagated":
        return
    try:
        from app.routers.feed import _event_to_item, _feed_user

        hub = get_feed_sse_hub()
        user = _feed_user(db, event.user_id)
        item = _event_to_item(event, user)
        hub.publish(
            event.user_id,
            event_name="feed_event",
            data=item.model_dump(mode="json"),
            event_id=event.id,
        )
    except Exception:
        logger.debug("feed_sse notify skipped", exc_info=True)
