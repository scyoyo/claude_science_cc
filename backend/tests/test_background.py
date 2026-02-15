"""Tests for background meeting runner and related API endpoints."""

import time
import threading
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models import Team, Agent, Meeting, MeetingMessage, MeetingStatus
from app.core.background_runner import (
    start_background_run,
    is_running,
    cleanup_stuck_meetings,
    _running,
    _lock,
)
from app.core.event_bus import subscribe, unsubscribe, clear_all as clear_event_bus


TEST_DATABASE_URL = "sqlite:///./test.db"


def _get_session_factory():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _create_team_and_meeting(client: TestClient) -> tuple[str, str]:
    """Helper: create a team with agents and a meeting, return (team_id, meeting_id)."""
    team = client.post("/api/teams/", json={"name": "BG Test Team"}).json()
    team_id = team["id"]

    client.post("/api/agents/", json={
        "team_id": team_id, "name": "Alice", "title": "Researcher",
        "expertise": "ML", "goal": "Research", "role": "lead", "model": "gpt-4",
    })
    client.post("/api/agents/", json={
        "team_id": team_id, "name": "Bob", "title": "Engineer",
        "expertise": "Systems", "goal": "Build", "role": "engineer", "model": "gpt-4",
    })

    meeting = client.post("/api/meetings/", json={
        "team_id": team_id, "title": "BG Meeting", "max_rounds": 3,
    }).json()

    return team_id, meeting["id"]


class TestBackgroundRunnerDirect:
    """Test background_runner module directly."""

    def test_start_and_complete(self, client):
        """Background run starts, stores messages, and updates status."""
        _, meeting_id = _create_team_and_meeting(client)
        session_factory = _get_session_factory()

        call_count = 0
        def mock_llm(system_prompt, messages):
            nonlocal call_count
            call_count += 1
            return f"Response {call_count}"

        started = start_background_run(
            meeting_id=meeting_id,
            session_factory=session_factory,
            rounds=2,
            topic="Test topic",
            llm_call_override=mock_llm,
        )
        assert started is True

        # Wait for completion
        for _ in range(50):
            if not is_running(meeting_id):
                break
            time.sleep(0.1)

        assert not is_running(meeting_id)

        # Verify messages were stored
        db = session_factory()
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        assert meeting.current_round == 2
        assert meeting.status in (MeetingStatus.pending.value, MeetingStatus.completed.value)

        messages = db.query(MeetingMessage).filter(MeetingMessage.meeting_id == meeting_id).all()
        # 2 agents * 2 rounds = 4 messages
        assert len(messages) == 4
        db.close()

    def test_prevent_duplicate_run(self, client):
        """Cannot start a second background run for the same meeting."""
        _, meeting_id = _create_team_and_meeting(client)
        session_factory = _get_session_factory()

        # Use a slow LLM to keep the first run alive
        barrier = threading.Event()
        def slow_llm(system_prompt, messages):
            barrier.wait(timeout=5)
            return "Slow response"

        started1 = start_background_run(
            meeting_id=meeting_id,
            session_factory=session_factory,
            rounds=1,
            llm_call_override=slow_llm,
        )
        assert started1 is True
        assert is_running(meeting_id)

        started2 = start_background_run(
            meeting_id=meeting_id,
            session_factory=session_factory,
            rounds=1,
            llm_call_override=slow_llm,
        )
        assert started2 is False

        # Release the barrier so the thread can finish
        barrier.set()
        for _ in range(50):
            if not is_running(meeting_id):
                break
            time.sleep(0.1)

    def test_failure_sets_failed_status(self, client):
        """If LLM call raises, meeting status is set to failed."""
        _, meeting_id = _create_team_and_meeting(client)
        session_factory = _get_session_factory()

        def failing_llm(system_prompt, messages):
            raise RuntimeError("LLM exploded")

        start_background_run(
            meeting_id=meeting_id,
            session_factory=session_factory,
            rounds=1,
            llm_call_override=failing_llm,
        )

        for _ in range(50):
            if not is_running(meeting_id):
                break
            time.sleep(0.1)

        db = session_factory()
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        assert meeting.status == MeetingStatus.failed.value
        db.close()

    def test_publishes_sse_events(self, client):
        """Background run publishes message, round_complete, meeting_complete events."""
        _, meeting_id = _create_team_and_meeting(client)
        session_factory = _get_session_factory()

        clear_event_bus()
        q = subscribe(meeting_id)

        call_count = 0
        def mock_llm(system_prompt, messages):
            nonlocal call_count
            call_count += 1
            return f"Response {call_count}"

        start_background_run(
            meeting_id=meeting_id,
            session_factory=session_factory,
            rounds=1,
            topic="SSE test",
            llm_call_override=mock_llm,
        )

        for _ in range(50):
            if not is_running(meeting_id):
                break
            time.sleep(0.1)

        # Collect all events
        events = []
        from queue import Empty
        while True:
            try:
                events.append(q.get(timeout=0.5))
            except Empty:
                break

        unsubscribe(meeting_id, q)
        clear_event_bus()

        # Should have message events (2 agents) + round_complete + meeting_complete
        types = [e["type"] for e in events]
        assert types.count("message") == 2
        assert "round_complete" in types
        assert "meeting_complete" in types

        # Verify message event structure
        msg_events = [e for e in events if e["type"] == "message"]
        for e in msg_events:
            assert "agent_name" in e
            assert "content" in e
            assert "round_number" in e

    def test_publishes_error_event_on_failure(self, client):
        """Background run publishes error event when LLM fails."""
        _, meeting_id = _create_team_and_meeting(client)
        session_factory = _get_session_factory()

        clear_event_bus()
        q = subscribe(meeting_id)

        def failing_llm(system_prompt, messages):
            raise RuntimeError("LLM exploded")

        start_background_run(
            meeting_id=meeting_id,
            session_factory=session_factory,
            rounds=1,
            llm_call_override=failing_llm,
        )

        for _ in range(50):
            if not is_running(meeting_id):
                break
            time.sleep(0.1)

        events = []
        from queue import Empty
        while True:
            try:
                events.append(q.get(timeout=0.5))
            except Empty:
                break

        unsubscribe(meeting_id, q)
        clear_event_bus()

        types = [e["type"] for e in events]
        assert "error" in types
        error_event = next(e for e in events if e["type"] == "error")
        assert "detail" in error_event

    def test_max_rounds_respected(self, client):
        """Background run respects max_rounds and sets completed."""
        _, meeting_id = _create_team_and_meeting(client)
        session_factory = _get_session_factory()

        def mock_llm(system_prompt, messages):
            return "Done"

        # Run all 3 rounds
        start_background_run(
            meeting_id=meeting_id,
            session_factory=session_factory,
            rounds=3,
            llm_call_override=mock_llm,
        )

        for _ in range(50):
            if not is_running(meeting_id):
                break
            time.sleep(0.1)

        db = session_factory()
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        assert meeting.current_round == 3
        assert meeting.status == MeetingStatus.completed.value
        db.close()


class TestCleanupStuckMeetings:
    """Test cleanup_stuck_meetings."""

    def test_cleanup_resets_stuck(self, client):
        """Cleanup sets stuck running meetings to failed."""
        _, meeting_id = _create_team_and_meeting(client)
        session_factory = _get_session_factory()

        # Manually set meeting to running (simulating a crash)
        db = session_factory()
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        meeting.status = MeetingStatus.running.value
        db.commit()
        db.close()

        count = cleanup_stuck_meetings(session_factory)
        assert count == 1

        db = session_factory()
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        assert meeting.status == MeetingStatus.failed.value
        db.close()

    def test_cleanup_ignores_actually_running(self, client):
        """Cleanup does not touch meetings that are actually running in background."""
        _, meeting_id = _create_team_and_meeting(client)
        session_factory = _get_session_factory()

        barrier = threading.Event()
        def slow_llm(system_prompt, messages):
            barrier.wait(timeout=5)
            return "OK"

        start_background_run(
            meeting_id=meeting_id,
            session_factory=session_factory,
            rounds=1,
            llm_call_override=slow_llm,
        )

        # Meeting is actually running
        assert is_running(meeting_id)
        count = cleanup_stuck_meetings(session_factory)
        assert count == 0

        barrier.set()
        for _ in range(50):
            if not is_running(meeting_id):
                break
            time.sleep(0.1)


class TestBackgroundAPI:
    """Test the background run API endpoints."""

    def test_run_background_endpoint(self, client):
        """POST /meetings/{id}/run-background starts background run."""
        _, meeting_id = _create_team_and_meeting(client)

        # Patch start_background_run so we don't need real LLM
        with patch("app.api.meetings.start_background_run", return_value=True) as mock_start:
            resp = client.post(f"/api/meetings/{meeting_id}/run-background", json={"rounds": 2})
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "started"
            assert data["rounds"] == 2
            mock_start.assert_called_once()

    def test_run_background_already_running(self, client):
        """POST /meetings/{id}/run-background returns 409 if already running."""
        _, meeting_id = _create_team_and_meeting(client)

        with patch("app.api.meetings.is_running", return_value=True):
            resp = client.post(f"/api/meetings/{meeting_id}/run-background", json={"rounds": 1})
            assert resp.status_code == 409

    def test_run_background_completed_meeting(self, client):
        """POST /meetings/{id}/run-background returns 400 for completed meetings."""
        _, meeting_id = _create_team_and_meeting(client)

        # Complete the meeting
        client.put(f"/api/meetings/{meeting_id}", json={"max_rounds": 0})
        # Manually set completed
        session_factory = _get_session_factory()
        db = session_factory()
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        meeting.status = MeetingStatus.completed.value
        db.commit()
        db.close()

        resp = client.post(f"/api/meetings/{meeting_id}/run-background", json={"rounds": 1})
        assert resp.status_code == 400

    def test_run_background_not_found(self, client):
        """POST /meetings/xxx/run-background returns 404."""
        resp = client.post("/api/meetings/nonexistent/run-background", json={"rounds": 1})
        assert resp.status_code == 404

    def test_status_endpoint(self, client):
        """GET /meetings/{id}/status returns lightweight status."""
        _, meeting_id = _create_team_and_meeting(client)

        resp = client.get(f"/api/meetings/{meeting_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meeting_id"] == meeting_id
        assert data["status"] == "pending"
        assert data["current_round"] == 0
        assert data["max_rounds"] == 3
        assert data["message_count"] == 0
        assert data["background_running"] is False

    def test_status_not_found(self, client):
        """GET /meetings/xxx/status returns 404."""
        resp = client.get("/api/meetings/nonexistent/status")
        assert resp.status_code == 404

    def test_run_background_no_agents(self, client):
        """POST /meetings/{id}/run-background returns 400 if no agents."""
        team = client.post("/api/teams/", json={"name": "Empty Team"}).json()
        meeting = client.post("/api/meetings/", json={
            "team_id": team["id"], "title": "Empty Meeting", "max_rounds": 3,
        }).json()

        with patch("app.api.meetings.start_background_run", return_value=True):
            resp = client.post(f"/api/meetings/{meeting['id']}/run-background", json={"rounds": 1})
            assert resp.status_code == 400
