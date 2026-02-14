"""Tests for Enhanced Meeting Agenda System (Steps 2-6).

Covers:
- Smart Context / RAG (context_extractor)
- Individual Meeting + Critic
- Merge / Iteration Pattern (batch-run)
- Agenda Proposal Strategies
- Rewrite / Improve
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.meeting_engine import MeetingEngine
from app.core.context_extractor import extract_keywords_from_agenda, extract_relevant_context
from app.core.agenda_proposer import AgendaProposer
from app.schemas.onboarding import ChatMessage


# ==================== Step 2: Smart Context / RAG ====================


class TestContextExtractor:
    """Tests for keyword extraction and context filtering."""

    def test_extract_keywords_basic(self):
        keywords = extract_keywords_from_agenda("Build a protein folding pipeline")
        assert "protein" in keywords
        assert "folding" in keywords
        assert "pipeline" in keywords
        # Stop words excluded
        assert "a" not in keywords

    def test_extract_keywords_with_questions(self):
        keywords = extract_keywords_from_agenda(
            "Research plan",
            questions=["What algorithm should we use?", "How to evaluate accuracy?"],
        )
        assert "algorithm" in keywords
        assert "evaluate" in keywords
        assert "accuracy" in keywords

    def test_extract_keywords_empty(self):
        keywords = extract_keywords_from_agenda("")
        assert keywords == []

    def test_extract_keywords_no_duplicates(self):
        keywords = extract_keywords_from_agenda("protein protein protein")
        assert keywords.count("protein") == 1

    def test_extract_relevant_context_with_keywords(self, test_db):
        """Context extraction filters paragraphs by keywords."""
        from app.models import Team, Meeting, MeetingMessage

        team = Team(name="Test Team")
        test_db.add(team)
        test_db.flush()

        m = Meeting(team_id=team.id, title="Prior Meeting", status="completed", max_rounds=1)
        test_db.add(m)
        test_db.flush()

        # Add messages with different topics
        test_db.add(MeetingMessage(
            meeting_id=m.id, role="assistant", agent_name="Agent",
            content="The protein structure is important.\n\nThe weather is nice today.",
            round_number=1,
        ))
        test_db.commit()

        results = extract_relevant_context(test_db, [m.id], keywords=["protein"])
        assert len(results) == 1
        assert "protein" in results[0]["summary"].lower()
        # Non-matching paragraph should be excluded when keywords match
        assert "weather" not in results[0]["summary"]

    def test_extract_relevant_context_fallback(self, test_db):
        """Falls back to last assistant message when no keyword matches."""
        from app.models import Team, Meeting, MeetingMessage

        team = Team(name="Test Team")
        test_db.add(team)
        test_db.flush()

        m = Meeting(team_id=team.id, title="Prior Meeting", status="completed", max_rounds=1)
        test_db.add(m)
        test_db.flush()

        test_db.add(MeetingMessage(
            meeting_id=m.id, role="assistant", agent_name="Agent",
            content="General discussion about various topics.",
            round_number=1,
        ))
        test_db.commit()

        results = extract_relevant_context(test_db, [m.id], keywords=["nonexistent"])
        assert len(results) == 1
        assert "General discussion" in results[0]["summary"]

    def test_extract_relevant_context_max_chars(self, test_db):
        """Respects max_chars limit."""
        from app.models import Team, Meeting, MeetingMessage

        team = Team(name="Test Team")
        test_db.add(team)
        test_db.flush()

        m = Meeting(team_id=team.id, title="Prior", status="completed", max_rounds=1)
        test_db.add(m)
        test_db.flush()

        test_db.add(MeetingMessage(
            meeting_id=m.id, role="assistant", agent_name="Agent",
            content="X" * 5000,
            round_number=1,
        ))
        test_db.commit()

        results = extract_relevant_context(test_db, [m.id], max_chars=100)
        assert len(results) == 1
        assert len(results[0]["summary"]) <= 103  # 100 + "..."


class TestContextPreviewAPI:
    """Tests for the preview-context endpoint."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def team(self, client):
        return client.post("/api/teams/", json={"name": "Context Team"}).json()

    def test_preview_context_empty(self, client, team):
        m = client.post("/api/meetings/", json={
            "team_id": team["id"], "title": "No Context",
        }).json()
        resp = client.post(f"/api/meetings/{m['id']}/preview-context")
        assert resp.status_code == 200
        assert resp.json()["contexts"] == []
        assert resp.json()["total_chars"] == 0

    @patch("app.api.meetings.resolve_llm_call")
    def test_preview_context_with_data(self, mock_llm, client, team):
        mock_llm.return_value = lambda sp, msgs: "LLM response about protein folding"

        # Create agents
        for name in ["Lead", "Member"]:
            client.post("/api/agents/", json={
                "team_id": team["id"], "name": name, "title": "Researcher",
                "expertise": "bio", "goal": "test", "role": "tester", "model": "gpt-4",
            })

        # Create and run first meeting
        m1 = client.post("/api/meetings/", json={
            "team_id": team["id"], "title": "Prior Work", "max_rounds": 1,
        }).json()
        client.post(f"/api/meetings/{m1['id']}/run", json={"rounds": 1})

        # Create second meeting referencing first
        m2 = client.post("/api/meetings/", json={
            "team_id": team["id"], "title": "Follow-up",
            "agenda": "Continue protein research",
            "context_meeting_ids": [m1["id"]],
        }).json()

        resp = client.post(f"/api/meetings/{m2['id']}/preview-context")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["contexts"]) == 1
        assert data["total_chars"] > 0


# ==================== Step 3: Individual Meeting + Critic ====================


class TestIndividualMeetingEngine:
    """Tests for individual meeting engine (agent + critic)."""

    def _mock_llm(self, system_prompt, messages):
        return f"Response from: {system_prompt[:30]}"

    def test_individual_meeting_round_structure(self):
        """Individual meeting: agent + critic in non-final rounds, agent only in final."""
        engine = MeetingEngine(llm_call=self._mock_llm)
        agent = {"id": "a1", "name": "Dr. Bio", "system_prompt": "You are a biologist", "model": "gpt-4"}

        all_rounds = engine.run_individual_meeting(
            agent=agent, conversation_history=[], rounds=3,
            agenda="Analyze protein structure",
        )
        assert len(all_rounds) == 3
        # Round 0: agent + critic = 2
        assert len(all_rounds[0]) == 2
        assert all_rounds[0][0]["agent_name"] == "Dr. Bio"
        assert all_rounds[0][1]["agent_name"] == "Scientific Critic"
        # Round 1: agent + critic = 2
        assert len(all_rounds[1]) == 2
        # Final round: agent only = 1
        assert len(all_rounds[2]) == 1
        assert all_rounds[2][0]["agent_name"] == "Dr. Bio"

    def test_individual_meeting_critic_speaks(self):
        """Critic provides feedback in non-final rounds."""
        call_log = []

        def tracking_llm(system_prompt, messages):
            call_log.append(system_prompt[:20])
            return "Mock response"

        engine = MeetingEngine(llm_call=tracking_llm)
        agent = {"id": "a1", "name": "Agent", "system_prompt": "Agent prompt", "model": "gpt-4"}

        engine.run_individual_meeting(agent=agent, conversation_history=[], rounds=2)
        # Round 0: agent + critic, Round 1 (final): agent only = 3 calls
        assert len(call_log) == 3

    def test_individual_meeting_single_round(self):
        """Single round: agent only (it's both the first and final round)."""
        engine = MeetingEngine(llm_call=lambda s, m: "OK")
        agent = {"id": "a1", "name": "Agent", "system_prompt": "Prompt", "model": "gpt-4"}

        all_rounds = engine.run_individual_meeting(agent=agent, conversation_history=[], rounds=1)
        assert len(all_rounds) == 1
        assert len(all_rounds[0]) == 1  # Agent only, no critic


class TestIndividualMeetingAPI:
    """Tests for individual meeting API."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def team_with_agent(self, client):
        team = client.post("/api/teams/", json={"name": "Individual Team"}).json()
        agent = client.post("/api/agents/", json={
            "team_id": team["id"], "name": "Solo Agent", "title": "Expert",
            "expertise": "testing", "goal": "test", "role": "tester", "model": "gpt-4",
        }).json()
        return team, agent

    def test_create_individual_meeting(self, client, team_with_agent):
        team, agent = team_with_agent
        resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Individual Session",
            "meeting_type": "individual",
            "individual_agent_id": agent["id"],
            "agenda": "Review methodology",
            "max_rounds": 3,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["meeting_type"] == "individual"
        assert data["individual_agent_id"] == agent["id"]

    @patch("app.api.meetings.resolve_llm_call")
    def test_run_individual_meeting(self, mock_llm, client, team_with_agent):
        team, agent = team_with_agent
        mock_llm.return_value = lambda sp, msgs: "Mock individual response"

        m = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Run Individual",
            "meeting_type": "individual",
            "individual_agent_id": agent["id"],
            "agenda": "Analyze data",
            "max_rounds": 2,
        }).json()

        resp = client.post(f"/api/meetings/{m['id']}/run", json={"rounds": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        # Round 1: agent + critic = 2, Round 2 (final): agent only = 1 → 3 messages
        assert len(data["messages"]) == 3

    @patch("app.api.meetings.resolve_llm_call")
    def test_individual_meeting_has_critic_messages(self, mock_llm, client, team_with_agent):
        team, agent = team_with_agent
        mock_llm.return_value = lambda sp, msgs: "Response"

        m = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Critic Check",
            "meeting_type": "individual",
            "individual_agent_id": agent["id"],
            "agenda": "Test",
            "max_rounds": 2,
        }).json()

        resp = client.post(f"/api/meetings/{m['id']}/run", json={"rounds": 2})
        messages = resp.json()["messages"]
        agent_names = [m["agent_name"] for m in messages]
        assert "Scientific Critic" in agent_names
        assert agent["name"] in agent_names


# ==================== Step 4: Merge / Iteration Pattern ====================


class TestMergeEngine:
    """Tests for merge meeting engine."""

    def test_merge_meeting(self):
        engine = MeetingEngine(llm_call=lambda s, m: "Merged response")
        agents = [
            {"id": "lead", "name": "Lead", "system_prompt": "Lead", "model": "gpt-4"},
            {"id": "m1", "name": "Member", "system_prompt": "Member", "model": "gpt-4"},
        ]
        summaries = [
            {"title": "Iteration 1", "summary": "Found approach A works well."},
            {"title": "Iteration 2", "summary": "Approach B is more efficient."},
        ]
        all_rounds = engine.run_merge_meeting(
            agents=agents,
            source_summaries=summaries,
            conversation_history=[],
            rounds=2,
            agenda="Synthesize best approach",
        )
        assert len(all_rounds) == 2

    def test_merge_prompt_content(self):
        from app.core.meeting_prompts import create_merge_prompt
        prompt = create_merge_prompt(
            agenda="Best algorithm",
            source_summaries=[
                {"title": "Run 1", "summary": "Algorithm A"},
                {"title": "Run 2", "summary": "Algorithm B"},
            ],
        )
        assert "Run 1" in prompt
        assert "Run 2" in prompt
        assert "Algorithm A" in prompt
        assert "Synthesize" in prompt


class TestBatchRunAPI:
    """Tests for batch-run endpoint."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def team_with_meeting(self, client):
        team = client.post("/api/teams/", json={"name": "Batch Team"}).json()
        client.post("/api/agents/", json={
            "team_id": team["id"], "name": "Agent", "title": "R",
            "expertise": "t", "goal": "t", "role": "t", "model": "gpt-4",
        })
        meeting = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Template Meeting",
            "agenda": "Test agenda",
            "max_rounds": 3,
        }).json()
        return team, meeting

    def test_batch_run_creates_iterations(self, client, team_with_meeting):
        _, meeting = team_with_meeting
        resp = client.post("/api/meetings/batch-run", json={
            "meeting_id": meeting["id"],
            "num_iterations": 3,
            "auto_merge": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["iteration_meeting_ids"]) == 3
        assert data["merge_meeting_id"] is None

    def test_batch_run_creates_merge(self, client, team_with_meeting):
        _, meeting = team_with_meeting
        resp = client.post("/api/meetings/batch-run", json={
            "meeting_id": meeting["id"],
            "num_iterations": 2,
            "auto_merge": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["iteration_meeting_ids"]) == 2
        assert data["merge_meeting_id"] is not None

        # Verify merge meeting has correct type
        merge = client.get(f"/api/meetings/{data['merge_meeting_id']}").json()
        assert merge["meeting_type"] == "merge"
        assert set(merge["source_meeting_ids"]) == set(data["iteration_meeting_ids"])

    def test_batch_run_nonexistent(self, client):
        resp = client.post("/api/meetings/batch-run", json={
            "meeting_id": "nonexistent",
            "num_iterations": 2,
        })
        assert resp.status_code == 404

    @patch("app.api.meetings.resolve_llm_call")
    def test_run_merge_meeting(self, mock_llm, client, team_with_meeting):
        """Run a merge meeting that references completed source meetings."""
        team, meeting = team_with_meeting
        mock_llm.return_value = lambda sp, msgs: "Merged output"

        # Complete the template meeting first
        resp = client.post(f"/api/meetings/{meeting['id']}/run", json={"rounds": 3})
        assert resp.status_code == 200

        # Create merge meeting manually
        merge = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Merge Meeting",
            "meeting_type": "merge",
            "source_meeting_ids": [meeting["id"]],
            "agenda": "Synthesize",
            "max_rounds": 1,
        }).json()

        resp = client.post(f"/api/meetings/{merge['id']}/run", json={"rounds": 1})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"


# ==================== Step 5: Agenda Proposal Strategies ====================


class TestAgendaProposer:
    """Tests for AgendaProposer core logic."""

    def test_auto_generate(self):
        def mock_llm(sp, msgs):
            return '{"agenda": "ML Pipeline", "questions": ["What model?"], "rules": ["Be concise"]}'

        proposer = AgendaProposer(llm_call=mock_llm)
        result = proposer.auto_generate(
            agents=[{"name": "Alice", "title": "ML Engineer", "expertise": "ML"}],
            team_desc="ML Team",
            goal="Build a pipeline",
        )
        assert result["agenda"] == "ML Pipeline"
        assert len(result["questions"]) == 1
        assert len(result["rules"]) == 1
        assert result["suggested_rounds"] == 3  # default when not in response

    def test_auto_generate_with_suggested_rounds(self):
        def mock_llm(sp, msgs):
            return '{"agenda": "Deep analysis", "questions": ["Q1"], "rules": [], "suggested_rounds": 5}'

        proposer = AgendaProposer(llm_call=mock_llm)
        result = proposer.auto_generate(
            agents=[{"name": "Alice"}], team_desc="Team", goal="Analyze",
        )
        assert result["suggested_rounds"] == 5

    def test_auto_generate_suggested_rounds_clamped(self):
        """suggested_rounds is clamped to 1-10."""
        def mock_llm(sp, msgs):
            return '{"agenda": "Test", "questions": [], "rules": [], "suggested_rounds": 99}'

        proposer = AgendaProposer(llm_call=mock_llm)
        result = proposer.auto_generate(
            agents=[{"name": "A"}], team_desc="T", goal="G",
        )
        assert result["suggested_rounds"] == 10

    def test_auto_generate_fallback(self):
        def mock_llm(sp, msgs):
            return "Just a plain text agenda without JSON"

        proposer = AgendaProposer(llm_call=mock_llm)
        result = proposer.auto_generate(
            agents=[{"name": "Bob"}], team_desc="Team", goal="Goal",
        )
        assert result["agenda"] != ""
        assert isinstance(result["questions"], list)
        assert result["suggested_rounds"] == 3  # default fallback

    def test_agent_voting(self):
        def mock_llm(sp, msgs):
            return '["Item 1", "Item 2"]'

        proposer = AgendaProposer(llm_call=mock_llm)
        result = proposer.agent_voting(
            agents=[
                {"name": "Alice", "system_prompt": "You are Alice"},
                {"name": "Bob", "system_prompt": "You are Bob"},
            ],
            topic="ML research",
        )
        assert len(result["proposals"]) == 2
        assert result["proposals"][0]["agent_name"] == "Alice"
        assert len(result["proposals"][0]["proposals"]) == 2
        assert result["merged_agenda"] != ""

    def test_chain_recommend(self):
        def mock_llm(sp, msgs):
            return '{"agenda": "Follow-up on gaps", "questions": ["What gaps remain?"], "rules": []}'

        proposer = AgendaProposer(llm_call=mock_llm)
        result = proposer.chain_recommend(
            prev_meeting_summaries=[
                {"title": "Meeting 1", "summary": "Found several gaps in approach."},
            ],
        )
        assert "gaps" in result["agenda"].lower()

    def test_chain_recommend_empty(self):
        proposer = AgendaProposer(llm_call=lambda s, m: "")
        result = proposer.chain_recommend(prev_meeting_summaries=[])
        assert result["agenda"] == ""

    def test_recommend_strategy_with_prev(self):
        proposer = AgendaProposer(llm_call=lambda s, m: "")
        result = proposer.recommend_strategy(agents=[{"name": "A"}], has_prev=True, topic="Test")
        assert result["recommended"] == "chain"

    def test_recommend_strategy_many_agents(self):
        proposer = AgendaProposer(llm_call=lambda s, m: "")
        agents = [{"name": f"Agent{i}"} for i in range(5)]
        result = proposer.recommend_strategy(agents=agents, has_prev=False, topic="Test")
        assert result["recommended"] == "agent_voting"

    def test_recommend_strategy_default(self):
        proposer = AgendaProposer(llm_call=lambda s, m: "")
        agents = [{"name": "A"}, {"name": "B"}]
        result = proposer.recommend_strategy(agents=agents, has_prev=False, topic="Test")
        assert result["recommended"] == "ai_auto"


class TestAgendaStrategyAPI:
    """Tests for agenda strategy endpoints."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def team_with_agents(self, client):
        team = client.post("/api/teams/", json={"name": "Agenda Team"}).json()
        for name in ["Alice", "Bob"]:
            client.post("/api/agents/", json={
                "team_id": team["id"], "name": name, "title": "R",
                "expertise": "t", "goal": "t", "role": "t", "model": "gpt-4",
            })
        return team

    def test_recommend_strategy_endpoint(self, client, team_with_agents):
        resp = client.post("/api/meetings/agenda/recommend-strategy", json={
            "team_id": team_with_agents["id"],
            "topic": "ML research",
            "has_prev_meetings": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommended"] in ["ai_auto", "agent_voting", "chain"]
        assert len(data["reasoning"]) > 0

    def test_recommend_strategy_invalid_team(self, client):
        resp = client.post("/api/meetings/agenda/recommend-strategy", json={
            "team_id": "nonexistent",
            "topic": "Test",
        })
        assert resp.status_code == 404

    @patch("app.api.meetings.resolve_llm_call")
    def test_auto_generate_endpoint(self, mock_llm, client, team_with_agents):
        mock_llm.return_value = lambda sp, msgs: (
            '{"agenda": "Research plan", "questions": ["Q1"], "rules": ["R1"], "suggested_rounds": 4}'
        )
        resp = client.post("/api/meetings/agenda/auto-generate", json={
            "team_id": team_with_agents["id"],
            "goal": "Build ML pipeline",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["agenda"] != ""
        assert isinstance(data["questions"], list)
        assert data["suggested_rounds"] == 4

    @patch("app.api.meetings.resolve_llm_call")
    def test_auto_generate_with_participant_filter(self, mock_llm, client, team_with_agents):
        """When participant_agent_ids is provided, only those agents are described in the prompt."""
        captured_prompts = []

        def capturing_llm(sp, msgs):
            captured_prompts.append(msgs[0].content if msgs else "")
            return '{"agenda": "Filtered plan", "questions": [], "rules": [], "suggested_rounds": 2}'

        mock_llm.return_value = capturing_llm

        # Get agents for this team
        agents_resp = client.get(f"/api/agents/team/{team_with_agents['id']}")
        agents = agents_resp.json()["items"]
        alice = next(a for a in agents if a["name"] == "Alice")

        resp = client.post("/api/meetings/agenda/auto-generate", json={
            "team_id": team_with_agents["id"],
            "goal": "Solo work",
            "participant_agent_ids": [alice["id"]],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["agenda"] == "Filtered plan"
        assert data["suggested_rounds"] == 2
        # The prompt should mention Alice but not Bob
        assert "Alice" in captured_prompts[0]
        assert "Bob" not in captured_prompts[0]

    @patch("app.api.meetings.resolve_llm_call")
    def test_agent_voting_endpoint(self, mock_llm, client, team_with_agents):
        mock_llm.return_value = lambda sp, msgs: '["Proposal 1", "Proposal 2"]'
        resp = client.post("/api/meetings/agenda/agent-voting", json={
            "team_id": team_with_agents["id"],
            "topic": "Data analysis",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["proposals"]) == 2
        assert data["merged_agenda"] != ""


# ==================== Step 6: Rewrite / Improve ====================


class TestRewriteAPI:
    """Tests for the rewrite endpoint."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def completed_meeting(self, client):
        team = client.post("/api/teams/", json={"name": "Rewrite Team"}).json()
        client.post("/api/agents/", json={
            "team_id": team["id"], "name": "Agent", "title": "R",
            "expertise": "t", "goal": "t", "role": "t", "model": "gpt-4",
        })

        with patch("app.api.meetings.resolve_llm_call") as mock:
            mock.return_value = lambda sp, msgs: "Original output content"
            m = client.post("/api/meetings/", json={
                "team_id": team["id"],
                "title": "Original Meeting",
                "agenda": "Build pipeline",
                "max_rounds": 1,
            }).json()
            client.post(f"/api/meetings/{m['id']}/run", json={"rounds": 1})

        return team, m

    def test_rewrite_creates_new_meeting(self, client, completed_meeting):
        team, original = completed_meeting
        resp = client.post(f"/api/meetings/{original['id']}/rewrite", json={
            "feedback": "Need more detail on error handling",
            "rounds": 2,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["parent_meeting_id"] == original["id"]
        assert data["rewrite_feedback"] == "Need more detail on error handling"
        assert data["max_rounds"] == 2
        assert "(rewrite)" in data["title"]
        # Original config preserved
        assert data["agenda"] == "Build pipeline"

    def test_rewrite_injects_context(self, client, completed_meeting):
        team, original = completed_meeting
        resp = client.post(f"/api/meetings/{original['id']}/rewrite", json={
            "feedback": "Improve code quality",
        })
        assert resp.status_code == 201
        rewrite_id = resp.json()["id"]

        # Get the rewrite meeting and check it has the context message
        rewrite = client.get(f"/api/meetings/{rewrite_id}").json()
        assert len(rewrite["messages"]) == 1
        assert "Rewrite / Improve" in rewrite["messages"][0]["content"]
        assert "Original Output" in rewrite["messages"][0]["content"]

    def test_rewrite_rejects_non_completed(self, client):
        team = client.post("/api/teams/", json={"name": "Non-complete Team"}).json()
        m = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Pending Meeting",
        }).json()

        resp = client.post(f"/api/meetings/{m['id']}/rewrite", json={
            "feedback": "Make it better",
        })
        assert resp.status_code == 400
        assert "completed" in resp.json()["detail"].lower()

    def test_rewrite_nonexistent(self, client):
        resp = client.post("/api/meetings/nonexistent/rewrite", json={
            "feedback": "Fix it",
        })
        assert resp.status_code == 404

    def test_rewrite_preserves_config(self, client, completed_meeting):
        team, original = completed_meeting
        resp = client.post(f"/api/meetings/{original['id']}/rewrite", json={
            "feedback": "More detail",
            "rounds": 3,
        })
        data = resp.json()
        assert data["team_id"] == original["team_id"]
        assert data["agenda"] == original["agenda"]


# ==================== Model Schema Tests ====================


class TestNewMeetingFields:
    """Tests for new meeting model fields."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def team(self, client):
        return client.post("/api/teams/", json={"name": "Fields Team"}).json()

    def test_default_values(self, client, team):
        m = client.post("/api/meetings/", json={
            "team_id": team["id"], "title": "Default Fields",
        }).json()
        assert m["meeting_type"] == "team"
        assert m["individual_agent_id"] is None
        assert m["source_meeting_ids"] == []
        assert m["parent_meeting_id"] is None
        assert m["rewrite_feedback"] == ""
        assert m["agenda_strategy"] == "manual"

    def test_set_meeting_type(self, client, team):
        m = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Merge Type",
            "meeting_type": "merge",
            "source_meeting_ids": ["id1", "id2"],
        }).json()
        assert m["meeting_type"] == "merge"
        assert m["source_meeting_ids"] == ["id1", "id2"]

    def test_update_agenda_strategy(self, client, team):
        m = client.post("/api/meetings/", json={
            "team_id": team["id"], "title": "Strategy Test",
        }).json()
        resp = client.put(f"/api/meetings/{m['id']}", json={
            "agenda_strategy": "ai_auto",
        })
        assert resp.status_code == 200
        assert resp.json()["agenda_strategy"] == "ai_auto"
