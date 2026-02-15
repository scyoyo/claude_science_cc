"""Tests for the event bus pub/sub module."""

import threading
import time
from queue import Empty

from app.core.event_bus import subscribe, unsubscribe, publish, clear_all, QUEUE_MAXSIZE


class TestEventBus:
    """Test event bus subscribe/unsubscribe/publish."""

    def setup_method(self):
        clear_all()

    def teardown_method(self):
        clear_all()

    def test_subscribe_and_publish(self):
        """Subscribe to a meeting and receive published events."""
        q = subscribe("m1")
        publish("m1", {"type": "message", "content": "hello"})
        event = q.get(timeout=1.0)
        assert event["type"] == "message"
        assert event["content"] == "hello"

    def test_unsubscribe_stops_events(self):
        """After unsubscribe, no more events are received."""
        q = subscribe("m1")
        unsubscribe("m1", q)
        publish("m1", {"type": "message", "content": "missed"})
        try:
            q.get(timeout=0.1)
            assert False, "Should not receive event after unsubscribe"
        except Empty:
            pass  # Expected

    def test_multiple_subscribers(self):
        """Multiple subscribers all receive the same event."""
        q1 = subscribe("m1")
        q2 = subscribe("m1")
        publish("m1", {"type": "message", "content": "broadcast"})
        e1 = q1.get(timeout=1.0)
        e2 = q2.get(timeout=1.0)
        assert e1["content"] == "broadcast"
        assert e2["content"] == "broadcast"

    def test_different_meetings_isolated(self):
        """Events for one meeting don't leak to another."""
        q1 = subscribe("m1")
        q2 = subscribe("m2")
        publish("m1", {"type": "message", "content": "for-m1"})
        e1 = q1.get(timeout=1.0)
        assert e1["content"] == "for-m1"
        try:
            q2.get(timeout=0.1)
            assert False, "Should not receive event for different meeting"
        except Empty:
            pass

    def test_queue_full_drops_event(self):
        """When queue is full, new events are silently dropped."""
        q = subscribe("m1")
        # Fill the queue
        for i in range(QUEUE_MAXSIZE):
            publish("m1", {"type": "message", "i": i})
        # Queue should be full — this publish should not raise
        publish("m1", {"type": "message", "i": "overflow"})
        # All original messages should be there
        assert q.qsize() == QUEUE_MAXSIZE

    def test_publish_no_subscribers(self):
        """Publishing with no subscribers does not raise."""
        publish("no-one-listening", {"type": "message"})

    def test_unsubscribe_nonexistent_queue(self):
        """Unsubscribing a queue that was never subscribed doesn't raise."""
        from queue import Queue
        q = Queue()
        unsubscribe("m1", q)  # Should not raise

    def test_clear_all(self):
        """clear_all removes all subscriptions."""
        q = subscribe("m1")
        clear_all()
        publish("m1", {"type": "message", "content": "after-clear"})
        try:
            q.get(timeout=0.1)
            assert False, "Should not receive event after clear_all"
        except Empty:
            pass

    def test_thread_safety(self):
        """Concurrent subscribe/publish/unsubscribe from multiple threads."""
        errors = []
        received = {"count": 0}
        lock = threading.Lock()

        def subscriber_thread(meeting_id: str, num_events: int):
            q = subscribe(meeting_id)
            for _ in range(num_events):
                try:
                    q.get(timeout=2.0)
                    with lock:
                        received["count"] += 1
                except Empty:
                    errors.append("Timeout waiting for event")
            unsubscribe(meeting_id, q)

        def publisher_thread(meeting_id: str, num_events: int):
            for i in range(num_events):
                publish(meeting_id, {"type": "message", "i": i})
                time.sleep(0.001)

        mid = "thread-test"
        num_subs = 3
        num_events = 10

        threads = []
        for _ in range(num_subs):
            t = threading.Thread(target=subscriber_thread, args=(mid, num_events))
            threads.append(t)
            t.start()

        # Give subscribers time to subscribe
        time.sleep(0.05)

        pub = threading.Thread(target=publisher_thread, args=(mid, num_events))
        pub.start()
        pub.join()

        for t in threads:
            t.join(timeout=5.0)

        assert not errors, f"Errors: {errors}"
        assert received["count"] == num_subs * num_events
