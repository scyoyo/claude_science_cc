"""Tests for Meeting Execution Engine (V1 + V11).

Covers:
- MeetingEngine: round execution, multi-round meetings (mocked LLM)
- MeetingEngine structured mode: phase-aware discussion
- Meeting API: CRUD, user messages, meeting run (mocked LLM)
- Structured meeting creation with agenda fields
- Auto-extraction of artifacts on completion
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.meeting_engine import MeetingEngine
from app.schemas.onboarding import ChatMessage


# ==================== MeetingEngine Unit Tests ====================


class TestMeetingEngine:
    """Tests for MeetingEngine core logic (legacy mode)."""

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


class TestMeetingEngineLanguage:
    """Tests for language support in legacy meeting mode."""

    def test_run_round_with_preferred_lang_zh(self):
        """Legacy run_round should inject Chinese language instruction."""
        received = []

        def tracking_llm(system_prompt, messages):
            received.append([m.content for m in messages])
            return "OK"

        engine = MeetingEngine(llm_call=tracking_llm)
        agents = [
            {"id": "a1", "name": "Agent A", "system_prompt": "You are A", "model": "gpt-4"},
        ]
        engine.run_round(agents, [], topic="Test topic", preferred_lang="zh")
        # Should have topic + language instruction
        assert any("中文" in c for c in received[0])

    def test_run_round_no_lang_when_history_exists(self):
        """Language instruction should not be injected when conversation_history is non-empty."""
        received = []

        def tracking_llm(system_prompt, messages):
            received.append([m.content for m in messages])
            return "OK"

        engine = MeetingEngine(llm_call=tracking_llm)
        agents = [
            {"id": "a1", "name": "Agent A", "system_prompt": "You are A", "model": "gpt-4"},
        ]
        history = [ChatMessage(role="user", content="Previous message")]
        engine.run_round(agents, history, preferred_lang="zh")
        # Should NOT inject language instruction because history already exists
        assert not any("中文" in c for c in received[0])

    def test_run_meeting_legacy_with_preferred_lang(self):
        """Legacy run_meeting passes preferred_lang to first round only."""
        received = []

        def tracking_llm(system_prompt, messages):
            received.append([m.content for m in messages])
            return "OK"

        engine = MeetingEngine(llm_call=tracking_llm)
        agents = [
            {"id": "a1", "name": "Agent A", "system_prompt": "You are A", "model": "gpt-4"},
        ]
        engine.run_meeting(agents, [], rounds=2, topic="Test", preferred_lang="zh")
        # First round: should have lang instruction
        assert any("中文" in c for c in received[0])
        # Second round: should NOT have lang instruction (history exists now)
        assert not any("中文" in c for c in received[1])


class TestLangDetectAndPrompt:
    """Tests for lang_detect and prompt generation."""

    def test_meeting_preferred_lang_team_language_fallback(self):
        """team_language should be used as fallback when other signals are absent."""
        from app.core.lang_detect import meeting_preferred_lang
        result = meeting_preferred_lang([], None, None, team_language="zh")
        assert result == "zh"

    def test_meeting_preferred_lang_locale_over_team(self):
        """locale should take priority over team_language."""
        from app.core.lang_detect import meeting_preferred_lang
        result = meeting_preferred_lang([], None, "en", team_language="zh")
        assert result == "en"

    def test_meeting_preferred_lang_message_over_all(self):
        """Existing user messages should take highest priority."""
        from app.core.lang_detect import meeting_preferred_lang

        class FakeMsg:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        msgs = [FakeMsg("user", "我想研究基因编辑")]
        result = meeting_preferred_lang(msgs, None, "en", team_language="en")
        assert result == "zh"

    def test_generate_system_prompt_with_language_zh(self):
        """System prompt should include Chinese instruction."""
        from app.core.prompt import generate_system_prompt

        class FakeAgent:
            title = "Researcher"
            expertise = "biology"
            goal = "study genes"
            role = "lead researcher"

        prompt = generate_system_prompt(FakeAgent(), language="zh")
        assert "Chinese" in prompt
        assert "中文" in prompt

    def test_generate_system_prompt_without_language(self):
        """System prompt without language should not have language instruction."""
        from app.core.prompt import generate_system_prompt

        class FakeAgent:
            title = "Researcher"
            expertise = "biology"
            goal = "study genes"
            role = "lead researcher"

        prompt = generate_system_prompt(FakeAgent())
        assert "IMPORTANT" not in prompt

    def test_generate_system_prompt_en_no_instruction(self):
        """English is the default — no explicit instruction appended."""
        from app.core.prompt import generate_system_prompt

        class FakeAgent:
            title = "Researcher"
            expertise = "biology"
            goal = "study genes"
            role = "lead researcher"

        prompt = generate_system_prompt(FakeAgent(), language="en")
        assert "IMPORTANT" not in prompt


class TestStructuredMeetingEngine:
    """Tests for MeetingEngine structured mode."""

    def _mock_llm(self, system_prompt, messages):
        # Return last user message content for inspection
        return f"Response to: {messages[-1].content[:50]}"

    def test_structured_first_round_team_lead_and_members(self):
        """First round: team lead proposes, members respond."""
        engine = MeetingEngine(llm_call=self._mock_llm)
        agents = [
            {"id": "lead", "name": "Dr. Lead", "system_prompt": "Lead system", "model": "gpt-4"},
            {"id": "m1", "name": "Dr. Member", "system_prompt": "Member system", "model": "gpt-4"},
        ]
        messages = engine.run_structured_round(
            agents=agents,
            conversation_history=[],
            round_num=1,
            num_rounds=3,
            agenda="Build a pipeline",
            agenda_questions=["What algorithm?"],
        )
        # Lead + 1 member = 2 messages
        assert len(messages) == 2
        assert messages[0]["agent_name"] == "Dr. Lead"
        assert messages[1]["agent_name"] == "Dr. Member"

    def test_structured_final_round_only_lead(self):
        """Final round: only Team Lead speaks."""
        engine = MeetingEngine(llm_call=self._mock_llm)
        agents = [
            {"id": "lead", "name": "Dr. Lead", "system_prompt": "Lead system", "model": "gpt-4"},
            {"id": "m1", "name": "Dr. Member", "system_prompt": "Member system", "model": "gpt-4"},
        ]
        messages = engine.run_structured_round(
            agents=agents,
            conversation_history=[],
            round_num=3,
            num_rounds=3,
            agenda="Build a pipeline",
        )
        # Only lead speaks in final round
        assert len(messages) == 1
        assert messages[0]["agent_name"] == "Dr. Lead"

    def test_structured_meeting_start_context_injected(self):
        """First round should inject meeting start context."""
        received_prompts = []

        def tracking_llm(system_prompt, messages):
            received_prompts.append([m.content for m in messages])
            return "OK"

        engine = MeetingEngine(llm_call=tracking_llm)
        agents = [
            {"id": "lead", "name": "Dr. Lead", "system_prompt": "Lead", "model": "gpt-4"},
        ]
        engine.run_structured_round(
            agents=agents,
            conversation_history=[],
            round_num=1,
            num_rounds=3,
            agenda="Test agenda",
            agenda_questions=["Q1"],
            agenda_rules=["Rule1"],
        )
        # Lead should see meeting start context
        lead_msgs = received_prompts[0]
        context_found = any("Test agenda" in m for m in lead_msgs)
        assert context_found

    def test_structured_multi_round_meeting(self):
        """Run a full 3-round structured meeting."""
        call_count = 0

        def counting_llm(system_prompt, messages):
            nonlocal call_count
            call_count += 1
            return f"Response #{call_count}"

        engine = MeetingEngine(llm_call=counting_llm)
        agents = [
            {"id": "lead", "name": "Lead", "system_prompt": "Lead", "model": "gpt-4"},
            {"id": "m1", "name": "Member", "system_prompt": "Member", "model": "gpt-4"},
        ]
        all_rounds = engine.run_structured_meeting(
            agents=agents,
            conversation_history=[],
            rounds=3,
            agenda="Research plan",
            agenda_questions=["Q1"],
            output_type="code",
        )
        assert len(all_rounds) == 3
        # Round 1: lead + member = 2
        assert len(all_rounds[0]) == 2
        # Round 2: lead + member = 2
        assert len(all_rounds[1]) == 2
        # Round 3 (final): lead only = 1
        assert len(all_rounds[2]) == 1

    def test_structured_empty_agents(self):
        """Structured round with no agents returns empty."""
        engine = MeetingEngine(llm_call=lambda s, m: "OK")
        messages = engine.run_structured_round([], [], 1, 3)
        assert messages == []

    def test_structured_single_agent(self):
        """With only one agent (lead, no members), lead speaks every round."""
        engine = MeetingEngine(llm_call=lambda s, m: "OK")
        agents = [{"id": "lead", "name": "Lead", "system_prompt": "Lead", "model": "gpt-4"}]
        # Round 1: lead speaks (no members)
        msgs = engine.run_structured_round(agents, [], 1, 3, agenda="Test")
        assert len(msgs) == 1
        # Final round: lead speaks
        msgs = engine.run_structured_round(agents, [], 3, 3, agenda="Test")
        assert len(msgs) == 1


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

    def test_create_meeting_with_agenda(self, client, team):
        """Create a meeting with agenda fields."""
        resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Structured Meeting",
            "agenda": "Build a protein folding pipeline",
            "agenda_questions": ["What algorithm?", "What dataset?"],
            "output_type": "code",
            "max_rounds": 3,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["agenda"] == "Build a protein folding pipeline"
        assert data["agenda_questions"] == ["What algorithm?", "What dataset?"]
        assert data["output_type"] == "code"
        # Default rules should be auto-injected for code type
        assert len(data["agenda_rules"]) > 0

    def test_create_meeting_custom_rules(self, client, team):
        """Custom agenda_rules override defaults."""
        resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Custom Rules Meeting",
            "agenda": "Topic",
            "agenda_rules": ["Custom rule 1"],
            "output_type": "code",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["agenda_rules"] == ["Custom rule 1"]

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
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

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

    @patch("app.api.meetings.resolve_llm_call")
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

    @patch("app.api.meetings.resolve_llm_call")
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

    @patch("app.api.meetings.resolve_llm_call")
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

    @patch("app.api.meetings.resolve_llm_call")
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

    @patch("app.api.meetings.resolve_llm_call")
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

    @patch("app.api.meetings.resolve_llm_call")
    def test_run_structured_meeting_uses_agenda(self, mock_make_llm, client, team_with_agents):
        """Structured meeting with agenda uses phase-aware engine."""
        received_messages = []

        def tracking_llm(sp, msgs):
            received_messages.append([m.content for m in msgs])
            return "Structured response"

        mock_make_llm.return_value = tracking_llm

        meeting_resp = client.post("/api/meetings/", json={
            "team_id": team_with_agents["id"],
            "title": "Structured Meeting",
            "agenda": "Build ML pipeline",
            "agenda_questions": ["What model?"],
            "output_type": "code",
            "max_rounds": 1,
        })
        meeting_id = meeting_resp.json()["id"]

        resp = client.post(f"/api/meetings/{meeting_id}/run", json={"rounds": 1})
        assert resp.status_code == 200
        # Should have meeting start context in prompts
        all_msgs = [m for sublist in received_messages for m in sublist]
        assert any("Build ML pipeline" in m for m in all_msgs)

    @patch("app.api.meetings.resolve_llm_call")
    def test_auto_extract_on_completion(self, mock_make_llm, client, team_with_agents):
        """Artifacts are auto-extracted when a meeting completes."""
        mock_make_llm.return_value = lambda sp, msgs: (
            "Here is the code:\n```python\nprint('hello')\n```"
        )

        meeting_resp = client.post("/api/meetings/", json={
            "team_id": team_with_agents["id"],
            "title": "Code Meeting",
            "max_rounds": 1,
        })
        meeting_id = meeting_resp.json()["id"]

        resp = client.post(f"/api/meetings/{meeting_id}/run", json={"rounds": 1})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

        # Check artifacts were auto-extracted
        artifacts_resp = client.get(f"/api/artifacts/meeting/{meeting_id}")
        assert artifacts_resp.status_code == 200
        data = artifacts_resp.json()
        assert data["total"] > 0


# ==================== Meeting Chain Tests ====================


class TestMeetingChain:
    """Tests for meeting chain (context_meeting_ids) feature."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def team(self, client):
        return client.post("/api/teams/", json={"name": "Chain Team"}).json()

    def test_create_meeting_with_context(self, client, team):
        """Create a meeting with context_meeting_ids."""
        # Create first meeting
        m1 = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Meeting 1",
        }).json()

        # Create second meeting referencing first
        m2 = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Meeting 2",
            "context_meeting_ids": [m1["id"]],
        }).json()
        assert m2["context_meeting_ids"] == [m1["id"]]

    def test_create_meeting_without_context(self, client, team):
        """Create a meeting without context_meeting_ids defaults to empty."""
        m = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "No Context",
        }).json()
        assert m["context_meeting_ids"] == []

    def test_update_meeting_context(self, client, team):
        """Update context_meeting_ids on existing meeting."""
        m1 = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "First",
        }).json()
        m2 = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Second",
        }).json()

        resp = client.put(f"/api/meetings/{m2['id']}", json={
            "context_meeting_ids": [m1["id"]],
        })
        assert resp.status_code == 200
        assert resp.json()["context_meeting_ids"] == [m1["id"]]

    @patch("app.api.meetings.resolve_llm_call")
    def test_meeting_chain_injects_context(self, mock_make_llm, client, team):
        """Running a meeting with context_meeting_ids injects previous summaries."""
        received_messages = []

        def tracking_llm(sp, msgs):
            received_messages.append([m.content for m in msgs])
            return "Response with context"

        mock_make_llm.return_value = tracking_llm

        # Create agents
        for name in ["Lead", "Member"]:
            client.post("/api/agents/", json={
                "team_id": team["id"],
                "name": name,
                "title": "Researcher",
                "expertise": "testing",
                "goal": "test things",
                "role": "tester",
                "model": "gpt-4",
            })

        # Create and "complete" first meeting with a message
        m1 = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Previous Meeting",
            "max_rounds": 1,
        }).json()
        # Run meeting 1
        resp = client.post(f"/api/meetings/{m1['id']}/run", json={"rounds": 1})
        assert resp.status_code == 200

        # Reset tracking
        received_messages.clear()

        # Create second meeting with agenda and context
        m2 = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Follow-up Meeting",
            "agenda": "Continue from previous work",
            "context_meeting_ids": [m1["id"]],
            "max_rounds": 1,
        }).json()

        # Run meeting 2
        resp = client.post(f"/api/meetings/{m2['id']}/run", json={"rounds": 1})
        assert resp.status_code == 200

        # Check that context from previous meeting was injected
        all_msgs = [m for sublist in received_messages for m in sublist]
        assert any("Previous Meeting" in m for m in all_msgs)
        assert any("Context from Previous Meetings" in m for m in all_msgs)
