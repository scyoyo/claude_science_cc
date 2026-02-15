"""
Thread-safe pub/sub event bus for SSE streaming.

- Without REDIS_URL: in-memory (single process only).
- With REDIS_URL: Redis pub/sub so run-background and /stream can live on different workers.
Each meeting_id can have multiple subscribers. Events are delivered via queue.Queue per subscriber.

Replay buffer: recent events are buffered per meeting_id so that late subscribers (SSE connecting
after background run starts) can receive events they missed.
"""

import json
import logging
import threading
from collections import deque
from queue import Queue, Full

from typing import Any

logger = logging.getLogger(__name__)

# --- In-memory backend ---
_subscribers: dict[str, list[Queue]] = {}
_lock = threading.Lock()

QUEUE_MAXSIZE = 256

# --- Replay buffer: stores recent events per meeting so late subscribers can catch up ---
REPLAY_BUFFER_SIZE = 128  # max events to buffer per meeting
_replay_buffers: dict[str, deque] = {}
_replay_lock = threading.Lock()

# --- Redis backend (when REDIS_URL is set) ---
_redis_pub = None
_redis_pub_lock = threading.Lock()
_redis_subs: dict[str, list[dict]] = {}  # meeting_id -> list of {queue, conn, thread}
_redis_subs_lock = threading.Lock()

SSE_CHANNEL_PREFIX = "meeting:sse:"


def _use_redis() -> bool:
    try:
        from app.config import settings
        return bool(settings.REDIS_URL)
    except Exception:
        return False


def _get_redis_pub():
    """Lazy shared Redis connection for publishing."""
    global _redis_pub
    with _redis_pub_lock:
        if _redis_pub is None:
            from app.config import settings
            import redis
            _redis_pub = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return _redis_pub


def _redis_listener(meeting_id: str, channel: str, q: Queue, conn: Any) -> None:
    """Run in a thread: subscribe to channel and put messages into q. Stops when conn is closed."""
    try:
        pubsub = conn.pubsub()
        pubsub.subscribe(channel)
        for msg in pubsub.listen():
            if msg.get("type") == "message" and msg.get("data"):
                try:
                    event = json.loads(msg["data"])
                    try:
                        q.put_nowait(event)
                    except Full:
                        logger.debug("Event bus: queue full for meeting %s, dropping event", meeting_id)
                except (json.JSONDecodeError, TypeError):
                    pass
    except Exception as e:
        if "Connection" in str(type(e).__name__) or "closed" in str(e).lower():
            pass  # expected on unsubscribe
        else:
            logger.debug("Redis listener for %s stopped: %s", meeting_id, e)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def subscribe(meeting_id: str) -> Queue:
    """Create a new subscription queue for a meeting.

    Replays any buffered events into the queue so late subscribers don't miss events
    published before they connected (solves the SSE-connects-after-run-starts race).
    """
    if not _use_redis():
        q: Queue = Queue(maxsize=QUEUE_MAXSIZE)
        with _lock:
            if meeting_id not in _subscribers:
                _subscribers[meeting_id] = []
            _subscribers[meeting_id].append(q)
        # Replay buffered events into the new subscriber's queue
        with _replay_lock:
            buf = _replay_buffers.get(meeting_id)
            if buf:
                for event in buf:
                    try:
                        q.put_nowait(event)
                    except Full:
                        break
        return q

    # Redis path: one connection + listener thread per subscriber
    import redis
    from app.config import settings
    q: Queue = Queue(maxsize=QUEUE_MAXSIZE)
    channel = SSE_CHANNEL_PREFIX + meeting_id
    conn = redis.from_url(settings.REDIS_URL, decode_responses=True)
    t = threading.Thread(
        target=_redis_listener,
        args=(meeting_id, channel, q, conn),
        daemon=True,
    )
    t.start()
    with _redis_subs_lock:
        if meeting_id not in _redis_subs:
            _redis_subs[meeting_id] = []
        _redis_subs[meeting_id].append({"queue": q, "conn": conn, "thread": t})
    return q


def unsubscribe(meeting_id: str, q: Queue) -> None:
    """Remove a subscription queue."""
    if not _use_redis():
        with _lock:
            subs = _subscribers.get(meeting_id)
            if subs:
                try:
                    subs.remove(q)
                except ValueError:
                    pass
                if not subs:
                    del _subscribers[meeting_id]
        return

    with _redis_subs_lock:
        subs = _redis_subs.get(meeting_id)
        if not subs:
            return
        for i, sub in enumerate(subs):
            if sub["queue"] is q:
                conn = sub["conn"]
                subs.pop(i)
                if not subs:
                    del _redis_subs[meeting_id]
                break
        else:
            return
    try:
        conn.close()
    except Exception:
        pass


def publish(meeting_id: str, event: dict[str, Any]) -> None:
    """Broadcast an event to all subscribers for a meeting.

    Also stores the event in a replay buffer so late subscribers (SSE connecting
    after publish) can catch up on missed events. Terminal events (meeting_complete,
    error) clear the replay buffer after delivery.
    """
    # Always buffer the event (even without current subscribers)
    with _replay_lock:
        if meeting_id not in _replay_buffers:
            _replay_buffers[meeting_id] = deque(maxlen=REPLAY_BUFFER_SIZE)
        _replay_buffers[meeting_id].append(event)

    if not _use_redis():
        with _lock:
            subs = _subscribers.get(meeting_id)
            if not subs:
                return
            subs = list(subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except Full:
                logger.debug("Event bus: queue full for meeting %s, dropping event", meeting_id)

        # Clear buffer on terminal events (meeting is done, no more late subscribers)
        if event.get("type") in ("meeting_complete", "error"):
            with _replay_lock:
                _replay_buffers.pop(meeting_id, None)
        return

    try:
        client = _get_redis_pub()
        channel = SSE_CHANNEL_PREFIX + meeting_id
        client.publish(channel, json.dumps(event))
    except Exception as e:
        logger.warning("Event bus: Redis publish failed for meeting %s: %s", meeting_id, e)

    if event.get("type") in ("meeting_complete", "error"):
        with _replay_lock:
            _replay_buffers.pop(meeting_id, None)


def clear_replay_buffer(meeting_id: str) -> None:
    """Explicitly clear the replay buffer for a meeting (e.g. on new run start)."""
    with _replay_lock:
        _replay_buffers.pop(meeting_id, None)


def clear_all() -> None:
    """Remove all subscriptions and replay buffers. For testing only."""
    with _lock:
        _subscribers.clear()
    with _replay_lock:
        _replay_buffers.clear()
    with _redis_subs_lock:
        for meeting_id, subs in list(_redis_subs.items()):
            for sub in subs:
                try:
                    sub["conn"].close()
                except Exception:
                    pass
        _redis_subs.clear()
