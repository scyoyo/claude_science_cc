"""Tests for WebSocket meeting execution (V2 Phase 2.4).

Tests cover:
- Connection handling (non-existent meeting, unknown message types)
- User message persistence
- Round execution with mocked LLM (single/multi round, completion, topic)
- Error conditions (completed meeting, max rounds, no agents, no API keys)
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models import Team, Agent, Meeting, MeetingMessage, MeetingStatus

TEST_DATABASE_URL = "sqlite:///./test.db"


@pytest.fixture
def ws_env():
    """Provide TestClient with patched SessionLocal for WebSocket tests."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with patch("app.api.ws.SessionLocal", TestSessionLocal):
        with TestClient(app) as c:
            yield c, TestSessionLocal


def _make_team(db):
    team = Team(name="WS Team", description="For WebSocket tests")
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def _make_agent(db, team_id, name="Dr. Alpha"):
    agent = Agent(
        team_id=team_id,
        name=name,
        title="Researcher",
        expertise="Testing",
        goal="Test things",
        role="Lead",
        system_prompt="You are a test agent.",
        model="gpt-4",
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _make_meeting(db, team_id, status="pending", max_rounds=5, current_round=0):
    meeting = Meeting(
        team_id=team_id,
        title="WS Meeting",
        status=status,
        max_rounds=max_rounds,
        current_round=current_round,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


# ==================== Connection Tests ====================


class TestWebSocketConnection:
    def test_nonexistent_meeting(self, ws_env):
        client, _ = ws_env
        with client.websocket_connect("/ws/meetings/nonexistent-id") as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "not found" in data["detail"].lower()

    def test_unknown_message_type(self, ws_env):
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        meeting = _make_meeting(db, team.id)
        db.close()

        with client.websocket_connect(f"/ws/meetings/{meeting.id}") as ws:
            ws.send_json({"type": "foobar"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Unknown message type" in data["detail"]


# ==================== User Message Tests ====================


class TestUserMessage:
    def test_send_user_message(self, ws_env):
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        meeting = _make_meeting(db, team.id)
        mid = meeting.id
        db.close()

        with client.websocket_connect(f"/ws/meetings/{mid}") as ws:
            ws.send_json({"type": "user_message", "content": "Hello agents!"})
            data = ws.receive_json()
            assert data["type"] == "message_saved"
            assert data["content"] == "Hello agents!"
            assert data["role"] == "user"

        # Verify persisted
        db = SL()
        msgs = db.query(MeetingMessage).filter(MeetingMessage.meeting_id == mid).all()
        assert len(msgs) == 1
        assert msgs[0].content == "Hello agents!"
        assert msgs[0].role == "user"
        db.close()

    def test_empty_message_rejected(self, ws_env):
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        meeting = _make_meeting(db, team.id)
        db.close()

        with client.websocket_connect(f"/ws/meetings/{meeting.id}") as ws:
            ws.send_json({"type": "user_message", "content": ""})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Empty message" in data["detail"]


# ==================== Start Round Tests ====================


class TestStartRound:
    def test_completed_meeting_rejected(self, ws_env):
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        meeting = _make_meeting(db, team.id, status="completed")
        db.close()

        with client.websocket_connect(f"/ws/meetings/{meeting.id}") as ws:
            ws.send_json({"type": "start_round", "rounds": 1})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "already completed" in data["detail"].lower()

    def test_max_rounds_reached(self, ws_env):
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        meeting = _make_meeting(db, team.id, max_rounds=3, current_round=3)
        db.close()

        with client.websocket_connect(f"/ws/meetings/{meeting.id}") as ws:
            ws.send_json({"type": "start_round", "rounds": 1})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Max rounds reached" in data["detail"]

    def test_no_agents(self, ws_env):
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        meeting = _make_meeting(db, team.id)
        db.close()

        with client.websocket_connect(f"/ws/meetings/{meeting.id}") as ws:
            ws.send_json({"type": "start_round", "rounds": 1})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "No agents" in data["detail"]

    def test_no_api_key(self, ws_env):
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        _make_agent(db, team.id)
        meeting = _make_meeting(db, team.id)
        db.close()

        with client.websocket_connect(f"/ws/meetings/{meeting.id}") as ws:
            ws.send_json({"type": "start_round", "rounds": 1})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "No active API key" in data["detail"]

    def test_single_round_success(self, ws_env):
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        _make_agent(db, team.id, name="Dr. Alpha")
        _make_agent(db, team.id, name="Dr. Beta")
        meeting = _make_meeting(db, team.id, max_rounds=5)
        mid = meeting.id
        db.close()

        mock_llm = MagicMock(side_effect=lambda sp, msgs: f"Response from mock")

        with patch("app.api.ws.resolve_llm_call", return_value=mock_llm):
            with client.websocket_connect(f"/ws/meetings/{mid}") as ws:
                ws.send_json({"type": "start_round", "rounds": 1})

                # 2 agents × (agent_speaking + message) = 4 messages
                m1 = ws.receive_json()
                assert m1["type"] == "agent_speaking"
                assert m1["agent_name"] == "Dr. Alpha"

                m2 = ws.receive_json()
                assert m2["type"] == "message"
                assert m2["agent_name"] == "Dr. Alpha"
                assert m2["content"] == "Response from mock"

                m3 = ws.receive_json()
                assert m3["type"] == "agent_speaking"
                assert m3["agent_name"] == "Dr. Beta"

                m4 = ws.receive_json()
                assert m4["type"] == "message"
                assert m4["agent_name"] == "Dr. Beta"

                rc = ws.receive_json()
                assert rc["type"] == "round_complete"
                assert rc["round"] == 1

        # Verify DB
        db = SL()
        updated = db.query(Meeting).filter(Meeting.id == mid).first()
        assert updated.current_round == 1
        assert updated.status == MeetingStatus.pending.value
        msgs = db.query(MeetingMessage).filter(MeetingMessage.meeting_id == mid).all()
        assert len(msgs) == 2
        db.close()

    def test_round_completes_meeting(self, ws_env):
        """Running the last round marks meeting as completed."""
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        _make_agent(db, team.id, name="Dr. Final")
        meeting = _make_meeting(db, team.id, max_rounds=1, current_round=0)
        mid = meeting.id
        db.close()

        mock_llm = MagicMock(return_value="Final answer")

        with patch("app.api.ws.resolve_llm_call", return_value=mock_llm):
            with client.websocket_connect(f"/ws/meetings/{mid}") as ws:
                ws.send_json({"type": "start_round", "rounds": 1})

                ws.receive_json()  # agent_speaking
                ws.receive_json()  # message

                rc = ws.receive_json()
                assert rc["type"] == "round_complete"

                mc = ws.receive_json()
                assert mc["type"] == "meeting_complete"
                assert mc["status"] == "completed"

        db = SL()
        updated = db.query(Meeting).filter(Meeting.id == mid).first()
        assert updated.status == MeetingStatus.completed.value
        assert updated.current_round == 1
        db.close()

    def test_multiple_rounds(self, ws_env):
        """Run 3 rounds in one command."""
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        _make_agent(db, team.id, name="Dr. Solo")
        meeting = _make_meeting(db, team.id, max_rounds=5)
        mid = meeting.id
        db.close()

        call_count = 0

        def mock_llm(sp, msgs):
            nonlocal call_count
            call_count += 1
            return f"Response {call_count}"

        with patch("app.api.ws.resolve_llm_call", return_value=mock_llm):
            with client.websocket_connect(f"/ws/meetings/{mid}") as ws:
                ws.send_json({"type": "start_round", "rounds": 3})

                for round_num in range(1, 4):
                    d = ws.receive_json()
                    assert d["type"] == "agent_speaking"

                    d = ws.receive_json()
                    assert d["type"] == "message"
                    assert d["content"] == f"Response {round_num}"

                    d = ws.receive_json()
                    assert d["type"] == "round_complete"
                    assert d["round"] == round_num

        db = SL()
        updated = db.query(Meeting).filter(Meeting.id == mid).first()
        assert updated.current_round == 3
        msgs = db.query(MeetingMessage).filter(MeetingMessage.meeting_id == mid).all()
        assert len(msgs) == 3
        db.close()

    def test_round_with_topic(self, ws_env):
        """Topic is passed through to the meeting engine."""
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        _make_agent(db, team.id, name="Dr. Topic")
        meeting = _make_meeting(db, team.id)
        mid = meeting.id
        db.close()

        captured_args = []

        def mock_llm(sp, msgs):
            captured_args.append((sp, [str(m) for m in msgs]))
            return "Topic response"

        with patch("app.api.ws.resolve_llm_call", return_value=mock_llm):
            with client.websocket_connect(f"/ws/meetings/{mid}") as ws:
                ws.send_json({"type": "start_round", "rounds": 1, "topic": "Gene editing"})

                ws.receive_json()  # agent_speaking
                ws.receive_json()  # message
                ws.receive_json()  # round_complete

        # The MeetingEngine adds "Discussion topic: {topic}" as first message
        assert len(captured_args) == 1
        assert any("Gene editing" in s for s in captured_args[0][1])

    def test_execution_failure_sets_status_failed(self, ws_env):
        """LLM failure during execution marks meeting as failed."""
        client, SL = ws_env
        db = SL()
        team = _make_team(db)
        _make_agent(db, team.id)
        meeting = _make_meeting(db, team.id)
        mid = meeting.id
        db.close()

        def broken_llm(sp, msgs):
            raise Exception("LLM exploded")

        with patch("app.api.ws.resolve_llm_call", return_value=broken_llm):
            with client.websocket_connect(f"/ws/meetings/{mid}") as ws:
                ws.send_json({"type": "start_round", "rounds": 1})
                data = ws.receive_json()
                assert data["type"] == "error"
                assert "Execution failed" in data["detail"]

        db = SL()
        updated = db.query(Meeting).filter(Meeting.id == mid).first()
        assert updated.status == MeetingStatus.failed.value
        db.close()
