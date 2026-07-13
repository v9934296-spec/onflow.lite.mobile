"""In-process SSE fan-out for feed updates (Step 10)."""
from __future__ import annotations

import json
import queue
import threading
from typing import Any

HEARTBEAT_INTERVAL_SECONDS = 30


class FeedSSEHub:
    """Thread-safe hub: sync publishers, async stream consumers via queue.get."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[queue.Queue[str]]] = {}

    def subscribe(self, user_id: str) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue()
        with self._lock:
            self._subscribers.setdefault(user_id, []).append(q)
        return q

    def unsubscribe(self, user_id: str, q: queue.Queue[str]) -> None:
        with self._lock:
            conns = self._subscribers.get(user_id, [])
            if q in conns:
                conns.remove(q)
            if not conns:
                self._subscribers.pop(user_id, None)

    @staticmethod
    def format_message(*, event_name: str, data: Any, event_id: str) -> str:
        payload = json.dumps(data, separators=(",", ":"), default=str)
        return f"event: {event_name}\nid: {event_id}\ndata: {payload}\n\n"

    def publish(
        self,
        user_id: str,
        *,
        event_name: str,
        data: Any,
        event_id: str,
    ) -> None:
        message = self.format_message(event_name=event_name, data=data, event_id=event_id)
        with self._lock:
            for q in self._subscribers.get(user_id, []):
                try:
                    q.put_nowait(message)
                except queue.Full:
                    pass

    def heartbeat_message(self) -> str:
        return "event: heartbeat\ndata: null\n\n"


_hub: FeedSSEHub | None = None


def get_feed_sse_hub() -> FeedSSEHub:
    global _hub
    if _hub is None:
        _hub = FeedSSEHub()
    return _hub


def reset_feed_sse_hub() -> None:
    """Test helper — replace the process-global hub."""
    global _hub
    _hub = FeedSSEHub()
