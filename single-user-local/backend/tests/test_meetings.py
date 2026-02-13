"""Tests for Meeting Execution Engine (Step 1.5).

Covers:
- MeetingEngine: round execution, multi-round meetings (mocked LLM)
- Meeting API: CRUD, user messages, meeting run (mocked LLM)
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.meeting_engine import MeetingEngine
from app.schemas.onboarding import ChatMessage


# ==================== MeetingEngine Unit Tests ====================


class TestMeetingEngine:
    """Tests for MeetingEngine core logic."""

    def _mock_llm(self, system_prompt, messages):
        """Simple mock that echoes a response based on the system prompt."""
        return f"Response from agent with prompt: {system_prompt[:30]}"

    def test_run_single_round(self):
        """Run one round with two agents."""
        engine = MeetingEngine(llm_call=self._mock_llm)
        agents = [
            {"id": "a1", "name": "Agent A", "system_prompt": "You are Agent A", "model": "gpt-4"},
            {"id": "a2", "name": "Agent B", "system_prompt": "You are Agent B", "model": "gpt-4"},
        ]
        messages = engine.run_round(agents, [], topic="Test topic")
        assert len(messages) == 2
        assert messages[0]["agent_name"] == "Agent A"
        assert messages[1]["agent_name"] == "Agent B"
        assert messages[0]["role"] == "assistant"

    def test_run_round_with_history(self):
        """Run a round with existing conversation history."""
        engine = MeetingEngine(llm_call=self._mock_llm)
        agents = [
            {"id": "a1", "name": "Agent A", "system_prompt": "You are Agent A", "model": "gpt-4"},
        ]
        history = [ChatMessage(role="user", content="Previous message")]
        messages = engine.run_round(agents, history)
        assert len(messages) == 1

    def test_run_multi_round_meeting(self):
        """Run a 3-round meeting."""
        call_count = 0

        def counting_llm(system_prompt, messages):
            nonlocal call_count
            call_count += 1
            return f"Response #{call_count}"

        engine = MeetingEngine(llm_call=counting_llm)
        agents = [
            {"id": "a1", "name": "Agent A", "system_prompt": "You are A", "model": "gpt-4"},
            {"id": "a2", "name": "Agent B", "system_prompt": "You are B", "model": "gpt-4"},
        ]
        all_rounds = engine.run_meeting(agents, [], rounds=3, topic="Research plan")
        assert len(all_rounds) == 3
        assert all(len(r) == 2 for r in all_rounds)
        # 2 agents * 3 rounds = 6 LLM calls
        assert call_count == 6

    def test_agents_see_previous_messages(self):
        """Second agent in a round should see the first agent's message."""
        received_messages = []

        def tracking_llm(system_prompt, messages):
            received_messages.append(len(messages))
            return "OK"

        engine = MeetingEngine(llm_call=tracking_llm)
        agents = [
            {"id": "a1", "name": "Agent A", "system_prompt": "A", "model": "gpt-4"},
            {"id": "a2", "name": "Agent B", "system_prompt": "B", "model": "gpt-4"},
        ]
        engine.run_round(agents, [], topic="Test")
        # Agent A sees: [topic message] = 1
        # Agent B sees: [topic message, Agent A's response] = 2
        assert received_messages[0] == 1
        assert received_messages[1] == 2


# ==================== Meeting API Tests ====================


class TestMeetingCRUDAPI:
    """Tests for meeting CRUD endpoints."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def team(self, client):
        """Create a test team."""
        resp = client.post("/api/teams/", json={"name": "Test Team"})
        return resp.json()

    @pytest.fixture
    def team_with_agents(self, client, team):
        """Create a team with agents."""
        for name in ["Agent A", "Agent B"]:
            client.post("/api/agents/", json={
                "team_id": team["id"],
                "name": name,
                "title": "Researcher",
                "expertise": "testing",
                "goal": "test things",
                "role": "tester",
                "model": "gpt-4",
            })
        return team

    def test_create_meeting(self, client, team):
        """Create a new meeting."""
        resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Sprint Planning",
            "description": "Plan next sprint",
            "max_rounds": 3,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Sprint Planning"
        assert data["status"] == "pending"
        assert data["max_rounds"] == 3
        assert data["current_round"] == 0

    def test_create_meeting_invalid_team(self, client):
        """Creating a meeting with invalid team returns 404."""
        resp = client.post("/api/meetings/", json={
            "team_id": "nonexistent",
            "title": "Bad Meeting",
        })
        assert resp.status_code == 404

    def test_get_meeting(self, client, team):
        """Get meeting with messages."""
        create_resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Test Meeting",
        })
        meeting_id = create_resp.json()["id"]

        resp = client.get(f"/api/meetings/{meeting_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Meeting"
        assert data["messages"] == []

    def test_get_nonexistent_meeting(self, client):
        """Get nonexistent meeting returns 404."""
        resp = client.get("/api/meetings/nonexistent")
        assert resp.status_code == 404

    def test_list_team_meetings(self, client, team):
        """List meetings for a team."""
        client.post("/api/meetings/", json={"team_id": team["id"], "title": "Meeting 1"})
        client.post("/api/meetings/", json={"team_id": team["id"], "title": "Meeting 2"})

        resp = client.get(f"/api/meetings/team/{team['id']}")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_meeting(self, client, team):
        """Update a meeting."""
        create_resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Old Title",
        })
        meeting_id = create_resp.json()["id"]

        resp = client.put(f"/api/meetings/{meeting_id}", json={"title": "New Title"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"

    def test_delete_meeting(self, client, team):
        """Delete a meeting."""
        create_resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "To Delete",
        })
        meeting_id = create_resp.json()["id"]

        resp = client.delete(f"/api/meetings/{meeting_id}")
        assert resp.status_code == 204

        resp = client.get(f"/api/meetings/{meeting_id}")
        assert resp.status_code == 404

    def test_add_user_message(self, client, team):
        """Add a user message to a meeting."""
        create_resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Interactive Meeting",
        })
        meeting_id = create_resp.json()["id"]

        resp = client.post(f"/api/meetings/{meeting_id}/message", json={
            "content": "What about using approach X?",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "user"
        assert data["content"] == "What about using approach X?"

        # Verify message appears in meeting
        meeting = client.get(f"/api/meetings/{meeting_id}").json()
        assert len(meeting["messages"]) == 1


class TestMeetingRunAPI:
    """Tests for meeting execution endpoint (mocked LLM)."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def team_with_agents(self, client):
        """Create a team with agents."""
        team_resp = client.post("/api/teams/", json={"name": "Research Team"})
        team = team_resp.json()
        for name in ["Lead Scientist", "Data Analyst"]:
            client.post("/api/agents/", json={
                "team_id": team["id"],
                "name": name,
                "title": "Researcher",
                "expertise": "testing",
                "goal": "test things",
                "role": "tester",
                "model": "gpt-4",
            })
        return team

    def test_run_meeting_no_api_key(self, client, team_with_agents):
        """Running a meeting without API keys fails gracefully."""
        meeting_resp = client.post("/api/meetings/", json={
            "team_id": team_with_agents["id"],
            "title": "Test Run",
        })
        meeting_id = meeting_resp.json()["id"]

        resp = client.post(f"/api/meetings/{meeting_id}/run", json={
            "rounds": 1,
            "topic": "Test discussion",
        })
        # Should fail because no API key is configured
        assert resp.status_code in [400, 502]

    @patch("app.api.meetings._make_llm_call")
    def test_run_meeting_success(self, mock_make_llm, client, team_with_agents):
        """Run a meeting with mocked LLM."""
        call_counter = 0

        def mock_llm_call(system_prompt, messages):
            nonlocal call_counter
            call_counter += 1
            return f"Mocked response #{call_counter}"

        mock_make_llm.return_value = mock_llm_call

        meeting_resp = client.post("/api/meetings/", json={
            "team_id": team_with_agents["id"],
            "title": "Mocked Meeting",
            "max_rounds": 5,
        })
        meeting_id = meeting_resp.json()["id"]

        resp = client.post(f"/api/meetings/{meeting_id}/run", json={
            "rounds": 2,
            "topic": "Discuss our research approach",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_round"] == 2
        assert data["status"] == "pending"  # Still has rounds remaining
        # 2 agents * 2 rounds = 4 messages
        assert len(data["messages"]) == 4

    @patch("app.api.meetings._make_llm_call")
    def test_run_meeting_completes(self, mock_make_llm, client, team_with_agents):
        """Meeting should mark as completed when max rounds reached."""
        mock_make_llm.return_value = lambda sp, msgs: "Mock response"

        meeting_resp = client.post("/api/meetings/", json={
            "team_id": team_with_agents["id"],
            "title": "Short Meeting",
            "max_rounds": 1,
        })
        meeting_id = meeting_resp.json()["id"]

        resp = client.post(f"/api/meetings/{meeting_id}/run", json={"rounds": 1})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    @patch("app.api.meetings._make_llm_call")
    def test_run_completed_meeting_fails(self, mock_make_llm, client, team_with_agents):
        """Cannot run a meeting that's already completed."""
        mock_make_llm.return_value = lambda sp, msgs: "Mock"

        meeting_resp = client.post("/api/meetings/", json={
            "team_id": team_with_agents["id"],
            "title": "Done Meeting",
            "max_rounds": 1,
        })
        meeting_id = meeting_resp.json()["id"]

        # Complete the meeting
        client.post(f"/api/meetings/{meeting_id}/run", json={"rounds": 1})

        # Try to run again
        resp = client.post(f"/api/meetings/{meeting_id}/run", json={"rounds": 1})
        assert resp.status_code == 400
        assert "already completed" in resp.json()["detail"]

    @patch("app.api.meetings._make_llm_call")
    def test_run_meeting_with_user_message(self, mock_make_llm, client, team_with_agents):
        """User messages should be included in meeting context."""
        received_messages_count = []

        def tracking_llm(sp, msgs):
            received_messages_count.append(len(msgs))
            return "Agent response"

        mock_make_llm.return_value = tracking_llm

        meeting_resp = client.post("/api/meetings/", json={
            "team_id": team_with_agents["id"],
            "title": "Interactive Meeting",
            "max_rounds": 5,
        })
        meeting_id = meeting_resp.json()["id"]

        # Add a user message first
        client.post(f"/api/meetings/{meeting_id}/message", json={
            "content": "Please focus on data quality",
        })

        # Run a round
        resp = client.post(f"/api/meetings/{meeting_id}/run", json={
            "rounds": 1,
            "topic": "Research planning",
        })
        assert resp.status_code == 200
        # Should have user message + 2 agent messages = 3
        assert len(resp.json()["messages"]) == 3

    def test_run_nonexistent_meeting(self, client):
        """Running a nonexistent meeting returns 404."""
        resp = client.post("/api/meetings/nonexistent/run", json={"rounds": 1})
        assert resp.status_code == 404

    @patch("app.api.meetings._make_llm_call")
    def test_run_meeting_no_agents(self, mock_make_llm, client):
        """Running a meeting with no agents fails."""
        mock_make_llm.return_value = lambda sp, msgs: "Mock"

        # Create team without agents
        team_resp = client.post("/api/teams/", json={"name": "Empty Team"})
        meeting_resp = client.post("/api/meetings/", json={
            "team_id": team_resp.json()["id"],
            "title": "Empty Meeting",
        })
        meeting_id = meeting_resp.json()["id"]

        resp = client.post(f"/api/meetings/{meeting_id}/run", json={"rounds": 1})
        assert resp.status_code == 400
        assert "No agents" in resp.json()["detail"]
