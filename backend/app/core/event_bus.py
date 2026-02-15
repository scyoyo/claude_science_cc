"""
Thread-safe in-memory pub/sub event bus for SSE streaming.

Each meeting_id can have multiple subscribers (SSE connections).
Events are delivered via queue.Queue per subscriber.
"""

import threading
import logging
from queue import Queue, Full
from typing import Any

logger = logging.getLogger(__name__)

_subscribers: dict[str, list[Queue]] = {}
_lock = threading.Lock()

QUEUE_MAXSIZE = 256


def subscribe(meeting_id: str) -> Queue:
    """Create a new subscription queue for a meeting. Returns the queue."""
    q: Queue = Queue(maxsize=QUEUE_MAXSIZE)
    with _lock:
        if meeting_id not in _subscribers:
            _subscribers[meeting_id] = []
        _subscribers[meeting_id].append(q)
    return q


def unsubscribe(meeting_id: str, q: Queue) -> None:
    """Remove a subscription queue."""
    with _lock:
        subs = _subscribers.get(meeting_id)
        if subs:
            try:
                subs.remove(q)
            except ValueError:
                pass
            if not subs:
                del _subscribers[meeting_id]


def publish(meeting_id: str, event: dict[str, Any]) -> None:
    """Broadcast an event to all subscribers for a meeting.

    If a subscriber's queue is full, the event is dropped for that subscriber.
    """
    with _lock:
        subs = _subscribers.get(meeting_id)
        if not subs:
            return
        # Copy list to avoid modification during iteration
        subs = list(subs)

    for q in subs:
        try:
            q.put_nowait(event)
        except Full:
            logger.debug("Event bus: queue full for meeting %s, dropping event", meeting_id)


def clear_all() -> None:
    """Remove all subscriptions. For testing only."""
    with _lock:
        _subscribers.clear()
