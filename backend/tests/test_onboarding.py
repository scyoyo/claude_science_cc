"""Tests for the Intelligent Onboarding System.

Covers:
- TeamBuilder: domain detection, problem analysis, team suggestion, mirror agents
- TeamBuilder LLM methods: clarifying response, propose team, explain mirrors
- MirrorValidator: response comparison, review flagging
- Onboarding API: multi-stage chat flow (template mode + LLM mode), team generation
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.team_builder import TeamBuilder, ANALYZER_PROMPT, TEAM_PROPOSER_PROMPT, MIRROR_ADVISOR_PROMPT
from app.core.mirror_validator import MirrorValidator
from app.schemas.onboarding import (
    AgentSuggestion,
    ChatMessage,
    DomainAnalysis,
    OnboardingStage,
)


# ==================== TeamBuilder Unit Tests ====================


class TestTeamBuilder:
    """Tests for TeamBuilder core logic."""

    def setup_method(self):
        self.builder = TeamBuilder()

    def test_detect_domain_biology(self):
        """Detect biology domain from keywords."""
        analysis = self.builder.analyze_problem(
            "I want to study gene expression in cancer cells using RNA sequencing"
        )
        assert analysis.domain == "biology"
        assert len(analysis.sub_domains) > 0
        assert len(analysis.key_challenges) > 0

    def test_detect_domain_ml(self):
        """Detect machine learning domain from keywords."""
        analysis = self.builder.analyze_problem(
            "I need to build a deep learning model for natural language processing"
        )
        assert analysis.domain == "machine_learning"

    def test_detect_domain_chemistry(self):
        """Detect chemistry domain from keywords."""
        analysis = self.builder.analyze_problem(
            "Design a molecular catalyst for organic synthesis reactions"
        )
        assert analysis.domain == "chemistry"

    def test_detect_domain_general(self):
        """Fall back to general domain when no keywords match."""
        analysis = self.builder.analyze_problem(
            "I want to analyze historical economic trends"
        )
        assert analysis.domain == "general"

    def test_suggest_team_composition(self):
        """Suggest team based on domain analysis."""
        analysis = DomainAnalysis(
            domain="biology",
            sub_domains=["genetics"],
            key_challenges=["data analysis"],
            suggested_approaches=["computational modeling"],
        )
        suggestion = self.builder.suggest_team_composition(analysis)
        assert suggestion.team_name == "Biology Research Team"
        assert len(suggestion.agents) > 0
        for agent in suggestion.agents:
            assert agent.name
            assert agent.title
            assert agent.model

    def test_suggest_team_with_preferences(self):
        """Respect user preferences in team suggestion."""
        analysis = DomainAnalysis(
            domain="machine_learning",
            sub_domains=["deep learning"],
            key_challenges=["model design"],
            suggested_approaches=["benchmark comparison"],
        )
        suggestion = self.builder.suggest_team_composition(
            analysis,
            preferences={"team_size": 2, "model": "claude-3-opus", "team_name": "My ML Team"},
        )
        assert suggestion.team_name == "My ML Team"
        assert len(suggestion.agents) == 2
        for agent in suggestion.agents:
            assert agent.model == "claude-3-opus"

    def test_create_mirror_agents(self):
        """Create mirror agents from primary agents."""
        primary = [
            AgentSuggestion(
                name="Lead Researcher",
                title="Senior Scientist",
                expertise="biology",
                goal="lead research",
                role="team lead",
                model="gpt-4",
            )
        ]
        mirrors = self.builder.create_mirror_agents(primary, "claude-3-opus")
        assert len(mirrors) == 1
        assert mirrors[0].name == "Lead Researcher (Mirror)"
        assert mirrors[0].model == "claude-3-opus"
        assert "verify" in mirrors[0].goal.lower()

    def test_auto_generate_team(self):
        """Auto-generate team from conversation history."""
        history = [
            ChatMessage(role="user", content="I need to study protein folding using machine learning"),
            ChatMessage(role="assistant", content="Great, let me analyze this..."),
        ]
        suggestion = self.builder.auto_generate_team(history, "Protein ML Team")
        assert suggestion.team_name == "Protein ML Team"
        assert len(suggestion.agents) > 0

    def test_llm_func_called_when_provided(self):
        """Verify LLM function is called when provided."""
        def mock_llm(prompt, history):
            return json.dumps({
                "domain": "physics",
                "sub_domains": ["quantum mechanics"],
                "key_challenges": ["simulation"],
                "suggested_approaches": ["monte carlo"],
            })

        builder = TeamBuilder(llm_func=mock_llm)
        analysis = builder.analyze_problem("quantum entanglement simulation")
        assert analysis.domain == "physics"
        assert "quantum mechanics" in analysis.sub_domains

    def test_llm_func_fallback_on_bad_json(self):
        """Fall back to template when LLM returns invalid JSON."""
        def bad_llm(prompt, history):
            return "not valid json"

        builder = TeamBuilder(llm_func=bad_llm)
        analysis = builder.analyze_problem("study gene expression in cells")
        # Should fall back to template-based analysis
        assert analysis.domain == "biology"


# ==================== TeamBuilder LLM Methods ====================


class TestTeamBuilderLLMMethods:
    """Tests for TeamBuilder LLM-powered methods."""

    def test_generate_clarifying_response_template_mode(self):
        """Without LLM, returns template analysis message."""
        builder = TeamBuilder()
        response = builder.generate_clarifying_response(
            "Study gene expression in cancer cells", []
        )
        assert "biology" in response.lower()
        assert "team" in response.lower()

    def test_generate_clarifying_response_llm_mode(self):
        """With LLM, calls llm_func with ANALYZER_PROMPT."""
        def mock_llm(prompt, history):
            assert "scientific research advisor" in prompt.lower() or any(
                "scientific research advisor" in m.content.lower() for m in history
                if m.role == "system"
            )
            return "Great question! A few things to clarify:\n1. What scale?\n2. What organisms?"

        builder = TeamBuilder(llm_func=mock_llm)
        response = builder.generate_clarifying_response("Study gene expression", [])
        assert "clarify" in response.lower()

    def test_propose_team_returns_none_without_llm(self):
        """Without LLM, propose_team returns None."""
        builder = TeamBuilder()
        result = builder.propose_team([ChatMessage(role="user", content="test")])
        assert result is None

    def test_propose_team_parses_json(self):
        """LLM returns team JSON wrapped in markdown fences."""
        team_json = {
            "team_name": "Genomics Team",
            "team_description": "A team for genomics research",
            "agents": [
                {
                    "name": "Genomics Lead",
                    "title": "Senior Genomicist",
                    "expertise": "genomics",
                    "goal": "lead genomics research",
                    "role": "principal investigator",
                    "model": "gpt-4",
                }
            ]
        }

        def mock_llm(prompt, history):
            return f"Here's my proposed team:\n```json\n{json.dumps(team_json)}\n```"

        builder = TeamBuilder(llm_func=mock_llm)
        result = builder.propose_team([ChatMessage(role="user", content="genomics research")])
        assert result is not None
        assert result.team_name == "Genomics Team"
        assert len(result.agents) == 1
        assert result.agents[0].name == "Genomics Lead"

    def test_propose_team_parses_raw_json(self):
        """LLM returns team JSON without markdown fences."""
        team_json = {
            "team_name": "ML Team",
            "team_description": "Machine learning research",
            "agents": [
                {
                    "name": "ML Lead",
                    "title": "ML Researcher",
                    "expertise": "deep learning",
                    "goal": "design models",
                    "role": "model architect",
                    "model": "gpt-4",
                }
            ]
        }

        def mock_llm(prompt, history):
            return f"I suggest this team: {json.dumps(team_json)}"

        builder = TeamBuilder(llm_func=mock_llm)
        result = builder.propose_team([ChatMessage(role="user", content="ML research")])
        assert result is not None
        assert result.team_name == "ML Team"

    def test_propose_team_returns_none_on_bad_json(self):
        """Returns None when LLM produces unparseable response."""
        def mock_llm(prompt, history):
            return "I'm not sure what team to suggest."

        builder = TeamBuilder(llm_func=mock_llm)
        result = builder.propose_team([ChatMessage(role="user", content="something")])
        assert result is None

    def test_propose_team_with_feedback(self):
        """Feedback message is appended to history."""
        calls = []

        def mock_llm(prompt, history):
            calls.append(history)
            return json.dumps({
                "team_name": "Revised Team",
                "team_description": "revised",
                "agents": [{
                    "name": "Agent", "title": "Title", "expertise": "exp",
                    "goal": "goal", "role": "role", "model": "gpt-4"
                }]
            })

        builder = TeamBuilder(llm_func=mock_llm)
        history = [ChatMessage(role="user", content="original request")]
        builder.propose_team(history, feedback="Add more agents")
        assert len(calls) == 1
        last_msg = calls[0][-1]
        assert last_msg.content == "Add more agents"
        assert last_msg.role == "user"

    def test_propose_team_with_text(self):
        """propose_team_with_text returns both suggestion and raw text."""
        raw_response = "Here's the team:\n```json\n" + json.dumps({
            "team_name": "Test Team",
            "team_description": "test",
            "agents": [{
                "name": "A", "title": "T", "expertise": "E",
                "goal": "G", "role": "R", "model": "gpt-4"
            }]
        }) + "\n```"

        def mock_llm(prompt, history):
            return raw_response

        builder = TeamBuilder(llm_func=mock_llm)
        suggestion, text = builder.propose_team_with_text(
            [ChatMessage(role="user", content="test")]
        )
        assert suggestion is not None
        assert suggestion.team_name == "Test Team"
        assert "Here's the team" in text

    def test_propose_team_with_text_no_llm(self):
        """propose_team_with_text returns (None, '') without LLM."""
        builder = TeamBuilder()
        suggestion, text = builder.propose_team_with_text(
            [ChatMessage(role="user", content="test")]
        )
        assert suggestion is None
        assert text == ""

    def test_explain_mirrors_template_mode(self):
        """Without LLM, returns static mirror explanation."""
        builder = TeamBuilder()
        response = builder.explain_mirrors([])
        assert "mirror" in response.lower()
        assert "model" in response.lower()

    def test_explain_mirrors_llm_mode(self):
        """With LLM, calls llm_func for mirror explanation."""
        def mock_llm(prompt, history):
            return "Mirror agents can cross-validate outputs. Want to enable them?"

        builder = TeamBuilder(llm_func=mock_llm)
        response = builder.explain_mirrors([ChatMessage(role="user", content="test")])
        assert "mirror" in response.lower()

    def test_build_messages_helper(self):
        """_build_messages creates proper message list."""
        history = [ChatMessage(role="user", content="hello")]
        messages = TeamBuilder._build_messages("system prompt", history, "new message")
        assert len(messages) == 3
        assert messages[0].role == "system"
        assert messages[0].content == "system prompt"
        assert messages[1].role == "user"
        assert messages[1].content == "hello"
        assert messages[2].role == "user"
        assert messages[2].content == "new message"

    def test_build_messages_without_user_message(self):
        """_build_messages works without optional user message."""
        history = [ChatMessage(role="user", content="hello")]
        messages = TeamBuilder._build_messages("system prompt", history)
        assert len(messages) == 2

    def test_parse_team_json_fenced(self):
        """_parse_team_json extracts JSON from markdown fences."""
        content = "Some text\n```json\n{\"team_name\": \"Test\"}\n```\nMore text"
        result = TeamBuilder._parse_team_json(content)
        assert result == {"team_name": "Test"}

    def test_parse_team_json_raw(self):
        """_parse_team_json extracts raw JSON object."""
        content = 'I suggest {"team_name": "Test"} for your research'
        result = TeamBuilder._parse_team_json(content)
        assert result == {"team_name": "Test"}

    def test_parse_team_json_none(self):
        """_parse_team_json returns None for non-JSON content."""
        result = TeamBuilder._parse_team_json("No JSON here at all")
        assert result is None

    def test_system_prompts_exist(self):
        """Verify system prompts are defined and non-empty."""
        assert len(ANALYZER_PROMPT) > 50
        assert len(TEAM_PROPOSER_PROMPT) > 50
        assert len(MIRROR_ADVISOR_PROMPT) > 50
        assert "clarifying" in ANALYZER_PROMPT.lower()
        assert "json" in TEAM_PROPOSER_PROMPT.lower()
        assert "mirror" in MIRROR_ADVISOR_PROMPT.lower()


# ==================== MirrorValidator Unit Tests ====================


class TestMirrorValidator:
    """Tests for MirrorValidator."""

    def setup_method(self):
        self.validator = MirrorValidator(review_threshold=0.5)

    def test_identical_responses(self):
        """Identical responses should have high similarity."""
        result = self.validator.compare_responses(
            "The protein folds into an alpha helix structure",
            "The protein folds into an alpha helix structure",
        )
        assert result.similarity_score == 1.0
        assert result.needs_review is False

    def test_similar_responses(self):
        """Similar responses should have moderate similarity."""
        result = self.validator.compare_responses(
            "The protein folds into an alpha helix structure with high stability",
            "The protein forms an alpha helix conformation that is very stable",
        )
        assert result.similarity_score > 0.2
        assert "protein" in result.key_agreements
        assert "alpha" in result.key_agreements

    def test_different_responses(self):
        """Very different responses should be flagged for review."""
        result = self.validator.compare_responses(
            "The experiment shows positive results with high confidence",
            "The data suggests we should try a completely different approach",
        )
        assert result.similarity_score < 0.5
        assert result.needs_review is True

    def test_empty_responses(self):
        """Both empty responses should be treated as identical."""
        result = self.validator.compare_responses("", "")
        assert result.similarity_score == 1.0
        assert result.needs_review is False

    def test_should_flag_for_review(self):
        """Test review threshold logic."""
        assert self.validator.should_flag_for_review(0.3) is True
        assert self.validator.should_flag_for_review(0.5) is False
        assert self.validator.should_flag_for_review(0.8) is False

    def test_custom_threshold(self):
        """Test with custom review threshold."""
        strict_validator = MirrorValidator(review_threshold=0.8)
        assert strict_validator.should_flag_for_review(0.7) is True
        assert strict_validator.should_flag_for_review(0.9) is False


# ==================== Onboarding API Tests (Template Mode) ====================


class TestOnboardingChatAPI:
    """Tests for the onboarding chat API in template mode (no LLM)."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    def test_problem_stage(self, client):
        """POST /api/onboarding/chat with problem stage."""
        response = client.post("/api/onboarding/chat", json={
            "stage": "problem",
            "message": "I want to study gene expression using RNA sequencing",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "problem"
        assert data["next_stage"] == "clarification"
        assert "analysis" in data["data"]
        assert "domain" in data["data"]["analysis"]
        assert data["data"]["analysis"]["domain"] == "biology"

    def test_clarification_stage(self, client):
        """POST /api/onboarding/chat with clarification stage."""
        response = client.post("/api/onboarding/chat", json={
            "stage": "clarification",
            "message": "I want a team of 3 using gpt-4",
            "context": {
                "analysis": {
                    "domain": "biology",
                    "sub_domains": ["genetics"],
                    "key_challenges": ["data analysis"],
                    "suggested_approaches": ["computational modeling"],
                },
                "preferences": {"team_size": 3, "model": "gpt-4"},
            },
        })
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "clarification"
        assert data["next_stage"] == "team_suggestion"
        assert "team_suggestion" in data["data"]
        assert "agents" in data["data"]["team_suggestion"]
        assert len(data["data"]["team_suggestion"]["agents"]) > 0

    def test_clarification_stage_missing_analysis(self, client):
        """Clarification stage fails without analysis context."""
        response = client.post("/api/onboarding/chat", json={
            "stage": "clarification",
            "message": "team of 3",
            "context": {},
        })
        assert response.status_code == 400
        assert "analysis" in response.json()["detail"].lower()

    def test_team_suggestion_stage(self, client):
        """POST /api/onboarding/chat with team_suggestion stage."""
        response = client.post("/api/onboarding/chat", json={
            "stage": "team_suggestion",
            "message": "Looks good, proceed with mirror agents",
            "context": {"team_suggestion": {"team_name": "Test Team", "agents": []}},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "team_suggestion"
        assert data["next_stage"] == "mirror_config"

    def test_mirror_config_stage(self, client):
        """POST /api/onboarding/chat with mirror_config stage."""
        response = client.post("/api/onboarding/chat", json={
            "stage": "mirror_config",
            "message": "Enable mirrors with claude-3-opus",
            "context": {
                "team_suggestion": {"team_name": "Test"},
                "mirror_config": {"enabled": True, "mirror_model": "claude-3-opus"},
            },
        })
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "mirror_config"
        assert data["next_stage"] == "complete"

    def test_complete_stage(self, client):
        """POST /api/onboarding/chat with complete stage."""
        response = client.post("/api/onboarding/chat", json={
            "stage": "complete",
            "message": "Done",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "complete"
        assert data["next_stage"] is None

    def test_full_chat_flow(self, client):
        """Test the complete multi-stage chat flow in template mode."""
        # Stage 1: Problem
        r1 = client.post("/api/onboarding/chat", json={
            "stage": "problem",
            "message": "Build a deep learning model for image classification",
        })
        assert r1.status_code == 200
        analysis = r1.json()["data"]["analysis"]
        assert analysis["domain"] == "machine_learning"

        # Stage 2: Clarification
        r2 = client.post("/api/onboarding/chat", json={
            "stage": "clarification",
            "message": "Team of 2 with gpt-4",
            "context": {
                "analysis": analysis,
                "preferences": {"team_size": 2, "model": "gpt-4"},
            },
        })
        assert r2.status_code == 200
        team_suggestion = r2.json()["data"]["team_suggestion"]
        assert len(team_suggestion["agents"]) == 2

        # Stage 3: Team suggestion
        r3 = client.post("/api/onboarding/chat", json={
            "stage": "team_suggestion",
            "message": "Accept",
            "context": {"team_suggestion": team_suggestion},
        })
        assert r3.status_code == 200

        # Stage 4: Mirror config
        r4 = client.post("/api/onboarding/chat", json={
            "stage": "mirror_config",
            "message": "No mirrors needed",
            "context": {"team_suggestion": team_suggestion, "mirror_config": {"enabled": False}},
        })
        assert r4.status_code == 200
        assert r4.json()["next_stage"] == "complete"

    def test_team_suggestion_reject_template(self, client):
        """Rejecting team in template mode returns re-ask message."""
        response = client.post("/api/onboarding/chat", json={
            "stage": "team_suggestion",
            "message": "No, I want to change the team composition",
            "context": {"team_suggestion": {"team_name": "Test", "agents": []}},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["next_stage"] == "team_suggestion"  # loops back
        assert "modify" in data["message"].lower() or "change" in data["message"].lower()


# ==================== Accept/Reject Detection Tests ====================


class TestAcceptRejectDetection:
    """Tests for _detect_accept_reject."""

    def test_accept_signals(self):
        from app.api.onboarding import _detect_accept_reject
        assert _detect_accept_reject("Yes, looks good") == "accept"
        assert _detect_accept_reject("I accept this team") == "accept"
        assert _detect_accept_reject("Proceed with this configuration") == "accept"
        assert _detect_accept_reject("Sure, go ahead") == "accept"

    def test_reject_signals(self):
        from app.api.onboarding import _detect_accept_reject
        assert _detect_accept_reject("No, I want to change something") == "reject"
        assert _detect_accept_reject("I reject this, modify it") == "reject"
        assert _detect_accept_reject("This is not good, revise please") == "reject"

    def test_unclear(self):
        from app.api.onboarding import _detect_accept_reject
        assert _detect_accept_reject("Tell me more about the agents") == "unclear"

    def test_mixed_signals_reject_wins(self):
        from app.api.onboarding import _detect_accept_reject
        # More reject than accept signals
        assert _detect_accept_reject("No, change and modify this") == "reject"


# ==================== Onboarding API Tests (LLM Mode) ====================


class TestOnboardingChatLLMMode:
    """Tests for the onboarding chat API with LLM enabled."""

    MOCK_TEAM_JSON = {
        "team_name": "Genomics Research Team",
        "team_description": "A team for studying gene expression",
        "agents": [
            {
                "name": "Genomics Lead",
                "title": "Senior Genomicist",
                "expertise": "genomics and gene expression",
                "goal": "lead genomics research",
                "role": "principal investigator",
                "model": "gpt-4",
            },
            {
                "name": "Bioinformatician",
                "title": "Data Scientist",
                "expertise": "bioinformatics pipelines",
                "goal": "process and analyze sequencing data",
                "role": "data analysis and pipeline development",
                "model": "gpt-4",
            },
        ],
    }

    def _make_mock_llm(self, responses=None):
        """Create a mock LLM function that returns predefined responses."""
        call_count = [0]
        default_responses = responses or []

        def mock_llm(prompt, history):
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(default_responses):
                return default_responses[idx]
            return "Default LLM response"

        return mock_llm

    @pytest.fixture
    def client_with_llm(self):
        """Create a test client with LLM mock injected via dependency override."""
        team_json_response = (
            f"Based on your research goals, here's my proposed team:\n"
            f"```json\n{json.dumps(self.MOCK_TEAM_JSON)}\n```\n"
            f"This team covers both experimental and computational aspects."
        )
        mock_llm = self._make_mock_llm([
            "Great question about gene expression! A few things I'd like to clarify:\n"
            "1. What specific organisms or cell types are you studying?\n"
            "2. Are you looking at bulk RNA-seq or single-cell?\n"
            "3. Do you have existing datasets or starting from scratch?",
            team_json_response,
            "Mirror agents can help cross-validate your team's outputs. Want to enable them?",
        ])

        def override_team_builder():
            return TeamBuilder(llm_func=mock_llm)

        from app.api.onboarding import get_team_builder
        app.dependency_overrides[get_team_builder] = override_team_builder
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.pop(get_team_builder, None)

    def test_problem_stage_llm(self, client_with_llm):
        """LLM mode: problem stage returns clarifying questions, no analysis data."""
        response = client_with_llm.post("/api/onboarding/chat", json={
            "stage": "problem",
            "message": "I want to study gene expression using RNA sequencing",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "problem"
        assert data["next_stage"] == "clarification"
        # LLM mode: no analysis in data, natural language response
        assert "analysis" not in data["data"]
        assert "clarify" in data["message"].lower()

    def test_clarification_stage_llm(self):
        """LLM mode: clarification stage proposes team as JSON."""
        team_json_response = (
            f"Based on your research goals, here's my proposed team:\n"
            f"```json\n{json.dumps(self.MOCK_TEAM_JSON)}\n```\n"
            f"This team covers both experimental and computational aspects."
        )
        mock_llm = self._make_mock_llm([team_json_response])

        from app.api.onboarding import get_team_builder
        app.dependency_overrides[get_team_builder] = lambda: TeamBuilder(llm_func=mock_llm)
        try:
            with TestClient(app) as client:
                response = client.post("/api/onboarding/chat", json={
                    "stage": "clarification",
                    "message": "We're studying human cancer cells with single-cell RNA-seq",
                    "conversation_history": [
                        {"role": "user", "content": "Study gene expression"},
                        {"role": "assistant", "content": "What organisms?"},
                    ],
                })
                assert response.status_code == 200
                data = response.json()
                assert data["stage"] == "clarification"
                assert data["next_stage"] == "team_suggestion"
                assert "team_suggestion" in data["data"]
                assert "proposed_team" in data["data"]
                assert len(data["data"]["proposed_team"]) == 2
                assert data["data"]["team_suggestion"]["team_name"] == "Genomics Research Team"
        finally:
            app.dependency_overrides.pop(get_team_builder, None)

    def test_team_suggestion_accept_llm(self):
        """LLM mode: accepting team triggers LLM mirror explanation."""
        mock_llm = self._make_mock_llm([
            "Mirror agents can help cross-validate your team's outputs. Want to enable them?"
        ])

        from app.api.onboarding import get_team_builder
        app.dependency_overrides[get_team_builder] = lambda: TeamBuilder(llm_func=mock_llm)
        try:
            with TestClient(app) as client:
                response = client.post("/api/onboarding/chat", json={
                    "stage": "team_suggestion",
                    "message": "Yes, looks good!",
                    "context": {"team_suggestion": self.MOCK_TEAM_JSON},
                    "conversation_history": [
                        {"role": "user", "content": "Study gene expression"},
                    ],
                })
                assert response.status_code == 200
                data = response.json()
                assert data["next_stage"] == "mirror_config"
                assert "mirror" in data["message"].lower()
        finally:
            app.dependency_overrides.pop(get_team_builder, None)

    def test_team_suggestion_reject_llm(self):
        """LLM mode: rejecting team triggers re-proposal."""
        revised_team = {
            "team_name": "Revised Genomics Team",
            "team_description": "Revised team",
            "agents": [
                {
                    "name": "New Lead",
                    "title": "Researcher",
                    "expertise": "genomics",
                    "goal": "research",
                    "role": "lead",
                    "model": "gpt-4",
                }
            ],
        }

        mock_llm = self._make_mock_llm([
            f"Here's a revised team:\n```json\n{json.dumps(revised_team)}\n```"
        ])

        from app.api.onboarding import get_team_builder

        def override():
            return TeamBuilder(llm_func=mock_llm)

        app.dependency_overrides[get_team_builder] = override
        try:
            with TestClient(app) as client:
                response = client.post("/api/onboarding/chat", json={
                    "stage": "team_suggestion",
                    "message": "No, I want to change the team. Add a statistician.",
                    "context": {"team_suggestion": self.MOCK_TEAM_JSON},
                    "conversation_history": [
                        {"role": "user", "content": "Study gene expression"},
                    ],
                })
                assert response.status_code == 200
                data = response.json()
                assert data["next_stage"] == "team_suggestion"  # loops back
                assert "team_suggestion" in data["data"]
                assert data["data"]["team_suggestion"]["team_name"] == "Revised Genomics Team"
        finally:
            app.dependency_overrides.pop(get_team_builder, None)

    def test_full_llm_flow(self):
        """Test complete multi-stage flow with LLM mock."""
        team_json = self.MOCK_TEAM_JSON
        team_json_response = f"Here's my team:\n```json\n{json.dumps(team_json)}\n```"

        call_idx = [0]
        responses = [
            "Interesting! Let me clarify:\n1. What scale?\n2. What tools?",
            team_json_response,
            "Mirror agents cross-validate outputs. Enable them?",
        ]

        def mock_llm(prompt, history):
            idx = call_idx[0]
            call_idx[0] += 1
            return responses[idx] if idx < len(responses) else "ok"

        from app.api.onboarding import get_team_builder

        def override():
            return TeamBuilder(llm_func=mock_llm)

        app.dependency_overrides[get_team_builder] = override
        try:
            with TestClient(app) as client:
                # Stage 1: Problem → clarifying questions
                r1 = client.post("/api/onboarding/chat", json={
                    "stage": "problem",
                    "message": "Study gene expression in cancer",
                })
                assert r1.status_code == 200
                assert r1.json()["next_stage"] == "clarification"
                assert "analysis" not in r1.json()["data"]

                # Stage 2: Clarification → team proposal
                r2 = client.post("/api/onboarding/chat", json={
                    "stage": "clarification",
                    "message": "Human cancer cells, single-cell RNA-seq",
                    "conversation_history": [
                        {"role": "user", "content": "Study gene expression in cancer"},
                        {"role": "assistant", "content": r1.json()["message"]},
                    ],
                })
                assert r2.status_code == 200
                assert r2.json()["next_stage"] == "team_suggestion"
                assert "proposed_team" in r2.json()["data"]

                # Stage 3: Accept team → mirror explanation
                r3 = client.post("/api/onboarding/chat", json={
                    "stage": "team_suggestion",
                    "message": "Accept",
                    "context": {"team_suggestion": r2.json()["data"]["team_suggestion"]},
                    "conversation_history": [
                        {"role": "user", "content": "Study gene expression in cancer"},
                        {"role": "assistant", "content": r1.json()["message"]},
                        {"role": "user", "content": "Human cancer cells"},
                        {"role": "assistant", "content": r2.json()["message"]},
                    ],
                })
                assert r3.status_code == 200
                assert r3.json()["next_stage"] == "mirror_config"

                # Stage 4: Mirror config → complete
                r4 = client.post("/api/onboarding/chat", json={
                    "stage": "mirror_config",
                    "message": "No mirrors",
                    "context": {
                        "team_suggestion": r2.json()["data"]["team_suggestion"],
                        "mirror_config": {"enabled": False},
                    },
                })
                assert r4.status_code == 200
                assert r4.json()["next_stage"] == "complete"
        finally:
            app.dependency_overrides.pop(get_team_builder, None)


# ==================== Parse Preferences Tests ====================


class TestParsePreferences:
    """Tests for _parse_preferences_from_message."""

    def test_extract_team_size_agents(self):
        from app.api.onboarding import _parse_preferences_from_message
        prefs = _parse_preferences_from_message("I want 5 agents")
        assert prefs["team_size"] == 5

    def test_extract_team_size_members(self):
        from app.api.onboarding import _parse_preferences_from_message
        prefs = _parse_preferences_from_message("Give me 3 members please")
        assert prefs["team_size"] == 3

    def test_extract_team_size_chinese(self):
        from app.api.onboarding import _parse_preferences_from_message
        prefs = _parse_preferences_from_message("我想要4个agent")
        assert prefs["team_size"] == 4

    def test_extract_team_size_team_of(self):
        from app.api.onboarding import _parse_preferences_from_message
        prefs = _parse_preferences_from_message("team of 3")
        assert prefs["team_size"] == 3

    def test_extract_model_gpt4(self):
        from app.api.onboarding import _parse_preferences_from_message
        prefs = _parse_preferences_from_message("I want to use gpt-4o for everything")
        assert prefs["model"] == "gpt-4o"

    def test_extract_model_claude(self):
        from app.api.onboarding import _parse_preferences_from_message
        prefs = _parse_preferences_from_message("use claude-3-opus please")
        assert prefs["model"] == "claude-3-opus"

    def test_extract_both(self):
        from app.api.onboarding import _parse_preferences_from_message
        prefs = _parse_preferences_from_message("3 agents with gpt-4")
        assert prefs["team_size"] == 3
        assert prefs["model"] == "gpt-4"

    def test_no_preferences(self):
        from app.api.onboarding import _parse_preferences_from_message
        prefs = _parse_preferences_from_message("Looks good, proceed")
        assert prefs == {}

    def test_invalid_size_ignored(self):
        from app.api.onboarding import _parse_preferences_from_message
        prefs = _parse_preferences_from_message("99 agents")
        assert "team_size" not in prefs


class TestOnboardingLLMFactory:
    """Tests for _create_onboarding_llm_func."""

    def test_no_api_key_returns_none(self):
        from app.api.onboarding import _create_onboarding_llm_func
        with patch("app.api.onboarding.settings") as mock_settings:
            mock_settings.ONBOARDING_API_KEY = ""
            mock_settings.ANTHROPIC_API_KEY = ""
            result = _create_onboarding_llm_func()
            assert result is None

    def test_fallback_to_anthropic_api_key(self):
        """When ONBOARDING_API_KEY is empty, falls back to ANTHROPIC_API_KEY."""
        from app.api.onboarding import _create_onboarding_llm_func
        with patch("app.api.onboarding.settings") as mock_settings, \
             patch("app.api.onboarding.create_provider") as mock_create:
            mock_settings.ONBOARDING_API_KEY = ""
            mock_settings.ANTHROPIC_API_KEY = "sk-ant-fallback"
            mock_settings.ONBOARDING_LLM_MODEL = "claude-sonnet-4-5-20250929"
            mock_create.return_value = MagicMock()
            result = _create_onboarding_llm_func()
            assert callable(result)
            mock_create.assert_called_once_with("anthropic", "sk-ant-fallback")

    def test_with_api_key_returns_callable(self):
        from app.api.onboarding import _create_onboarding_llm_func
        with patch("app.api.onboarding.settings") as mock_settings, \
             patch("app.api.onboarding.create_provider") as mock_create:
            mock_settings.ONBOARDING_API_KEY = "sk-test-key"
            mock_settings.ONBOARDING_LLM_PROVIDER = "anthropic"
            mock_settings.ONBOARDING_LLM_MODEL = "claude-sonnet-4-5-20250929"
            mock_provider = MagicMock()
            mock_create.return_value = mock_provider
            result = _create_onboarding_llm_func()
            assert callable(result)
            mock_create.assert_called_once_with("anthropic", "sk-test-key")

    def test_llm_func_calls_provider(self):
        from app.api.onboarding import _create_onboarding_llm_func
        from app.schemas.onboarding import ChatMessage
        with patch("app.api.onboarding.settings") as mock_settings, \
             patch("app.api.onboarding.create_provider") as mock_create:
            mock_settings.ONBOARDING_API_KEY = "sk-test-key"
            mock_settings.ONBOARDING_LLM_PROVIDER = "anthropic"
            mock_settings.ONBOARDING_LLM_MODEL = "test-model"
            mock_provider = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "LLM response"
            mock_provider.chat.return_value = mock_response
            mock_create.return_value = mock_provider

            llm_func = _create_onboarding_llm_func()
            result = llm_func("system prompt", [ChatMessage(role="user", content="hello")])
            assert result == "LLM response"
            mock_provider.chat.assert_called_once()


# ==================== Generate Team API Tests ====================


class TestGenerateTeamAPI:
    """Tests for the generate-team endpoint."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    def test_generate_team_basic(self, client):
        """Generate a team with agents."""
        response = client.post("/api/onboarding/generate-team", json={
            "team_name": "Biology Research Team",
            "team_description": "A team for studying gene expression",
            "agents": [
                {
                    "name": "Lead Scientist",
                    "title": "Senior Researcher",
                    "expertise": "molecular biology",
                    "goal": "lead the research",
                    "role": "principal investigator",
                    "model": "gpt-4",
                },
                {
                    "name": "Data Analyst",
                    "title": "Bioinformatician",
                    "expertise": "data analysis",
                    "goal": "analyze experimental data",
                    "role": "data processing and visualization",
                    "model": "gpt-4",
                },
            ],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Biology Research Team"
        assert len(data["agents"]) == 2
        # Verify system prompts were generated
        for agent in data["agents"]:
            assert agent["system_prompt"]
            assert len(agent["system_prompt"]) > 0

    def test_generate_team_with_mirrors(self, client):
        """Generate a team with mirror agents."""
        response = client.post("/api/onboarding/generate-team", json={
            "team_name": "ML Team with Mirrors",
            "team_description": "Cross-validated ML research",
            "agents": [
                {
                    "name": "ML Lead",
                    "title": "ML Researcher",
                    "expertise": "deep learning",
                    "goal": "design models",
                    "role": "model architecture",
                    "model": "gpt-4",
                },
            ],
            "mirror_config": {
                "enabled": True,
                "mirror_model": "claude-3-opus",
                "agents_to_mirror": [],
            },
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "ML Team with Mirrors"
        # Should have 1 primary + 1 mirror
        assert len(data["agents"]) == 2
        mirrors = [a for a in data["agents"] if a["is_mirror"]]
        assert len(mirrors) == 1
        assert mirrors[0]["model"] == "claude-3-opus"
        assert mirrors[0]["primary_agent_id"] is not None

    def test_generate_team_with_selective_mirrors(self, client):
        """Generate mirrors only for selected agents."""
        response = client.post("/api/onboarding/generate-team", json={
            "team_name": "Selective Mirror Team",
            "agents": [
                {
                    "name": "Agent A",
                    "title": "Researcher A",
                    "expertise": "area A",
                    "goal": "goal A",
                    "role": "role A",
                    "model": "gpt-4",
                },
                {
                    "name": "Agent B",
                    "title": "Researcher B",
                    "expertise": "area B",
                    "goal": "goal B",
                    "role": "role B",
                    "model": "gpt-4",
                },
            ],
            "mirror_config": {
                "enabled": True,
                "mirror_model": "gpt-4",
                "agents_to_mirror": ["Agent A"],
            },
        })
        assert response.status_code == 201
        data = response.json()
        # 2 primary + 1 mirror (only Agent A mirrored)
        assert len(data["agents"]) == 3
        mirrors = [a for a in data["agents"] if a["is_mirror"]]
        assert len(mirrors) == 1
        assert "Agent A" in mirrors[0]["name"]

    def test_generate_team_persists_to_db(self, client):
        """Verify generated team is accessible via existing API."""
        # Generate team
        gen_response = client.post("/api/onboarding/generate-team", json={
            "team_name": "Persistent Team",
            "agents": [
                {
                    "name": "Solo Agent",
                    "title": "Researcher",
                    "expertise": "general",
                    "goal": "research",
                    "role": "analyst",
                    "model": "gpt-4",
                },
            ],
        })
        assert gen_response.status_code == 201
        team_id = gen_response.json()["id"]

        # Verify via teams API
        team_response = client.get(f"/api/teams/{team_id}")
        assert team_response.status_code == 200
        assert team_response.json()["name"] == "Persistent Team"
        assert len(team_response.json()["agents"]) == 1
