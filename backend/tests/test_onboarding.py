"""Tests for the Intelligent Onboarding System (Step 1.0).

Covers:
- TeamBuilder: domain detection, problem analysis, team suggestion, mirror agents
- MirrorValidator: response comparison, review flagging
- Onboarding API: multi-stage chat flow, team generation
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.team_builder import TeamBuilder
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
        import json

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


# ==================== Onboarding API Tests ====================


class TestOnboardingChatAPI:
    """Tests for the onboarding chat API."""

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
        assert "domain" in data["data"]
        assert data["data"]["domain"] == "biology"

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
        assert "agents" in data["data"]
        assert len(data["data"]["agents"]) > 0

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
        """Test the complete multi-stage chat flow."""
        # Stage 1: Problem
        r1 = client.post("/api/onboarding/chat", json={
            "stage": "problem",
            "message": "Build a deep learning model for image classification",
        })
        assert r1.status_code == 200
        analysis = r1.json()["data"]
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
        team_suggestion = r2.json()["data"]
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
