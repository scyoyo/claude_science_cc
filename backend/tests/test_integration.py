"""Integration Tests: Full end-to-end API flows.

Simulates how the frontend calls backend APIs, testing complete
user workflows from team creation through meeting execution to export.
"""

import json
import zipfile
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestFullWorkflow:
    """Test the complete workflow as the frontend would use it."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    def test_full_team_creation_workflow(self, client):
        """Frontend flow: Create team -> Add agents -> Verify team detail."""
        # Step 1: Create a team (Teams page -> "New Team" button)
        team = client.post("/api/teams/", json={
            "name": "Protein Design Lab",
            "description": "AI agents for protein engineering",
        }).json()
        assert team["id"]
        assert team["name"] == "Protein Design Lab"

        # Step 2: Add agents (Team detail page -> "Add Agent" form)
        agent1 = client.post("/api/agents/", json={
            "team_id": team["id"],
            "name": "Dr. Structure",
            "title": "Structural Biologist",
            "expertise": "Protein folding and structure prediction",
            "goal": "Design stable protein structures",
            "role": "Lead structural analysis",
            "model": "gpt-4",
        }).json()
        assert agent1["system_prompt"]  # Auto-generated

        client.post("/api/agents/", json={
            "team_id": team["id"],
            "name": "Dr. Sequence",
            "title": "Sequence Analyst",
            "expertise": "Protein sequence analysis and alignment",
            "goal": "Optimize amino acid sequences",
            "role": "Sequence optimization specialist",
            "model": "claude-3-opus",
        })

        # Step 3: Get team with agents (Team detail page load)
        team_detail = client.get(f"/api/teams/{team['id']}").json()
        assert len(team_detail["agents"]) == 2
        agent_names = {a["name"] for a in team_detail["agents"]}
        assert agent_names == {"Dr. Structure", "Dr. Sequence"}

    def test_full_meeting_workflow(self, client):
        """Frontend flow: Create team -> Create meeting -> Add messages -> List."""
        # Setup: Create team with agents
        team = client.post("/api/teams/", json={"name": "ML Team"}).json()
        client.post("/api/agents/", json={
            "team_id": team["id"],
            "name": "Researcher",
            "title": "ML Researcher",
            "expertise": "Deep learning",
            "goal": "Design experiments",
            "role": "Research lead",
            "model": "gpt-4",
        })

        # Step 1: Create meeting (returns 201)
        resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Experiment Design",
            "description": "Design neural architecture search experiment",
            "max_rounds": 3,
        })
        assert resp.status_code == 201
        meeting = resp.json()
        assert meeting["status"] == "pending"
        assert meeting["max_rounds"] == 3

        # Step 2: Add user message (returns 201, single message)
        resp = client.post(f"/api/meetings/{meeting['id']}/message", json={
            "content": "Let's design a NAS experiment for image classification",
        })
        assert resp.status_code == 201
        msg = resp.json()
        assert msg["role"] == "user"

        # Step 3: Get meeting with messages (Meeting page load)
        meeting_detail = client.get(f"/api/meetings/{meeting['id']}").json()
        assert len(meeting_detail["messages"]) == 1

        # Step 4: List team meetings (Team detail -> meetings list)
        meetings_resp = client.get(f"/api/meetings/team/{team['id']}").json()
        assert meetings_resp["total"] == 1
        assert meetings_resp["items"][0]["title"] == "Experiment Design"

    def test_full_artifact_and_export_workflow(self, client):
        """Frontend flow: Create artifacts -> Export in all formats."""
        # Setup
        team = client.post("/api/teams/", json={"name": "Code Team"}).json()
        resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Code Generation",
        })
        assert resp.status_code == 201
        meeting = resp.json()

        # Step 1: Create artifacts (returns 201)
        resp = client.post("/api/artifacts/", json={
            "meeting_id": meeting["id"],
            "filename": "model.py",
            "language": "python",
            "content": "import torch\n\nclass MyModel(torch.nn.Module):\n    pass",
            "description": "Neural network model",
        })
        assert resp.status_code == 201

        resp = client.post("/api/artifacts/", json={
            "meeting_id": meeting["id"],
            "filename": "train.py",
            "language": "python",
            "content": "from model import MyModel\n\ndef train():\n    model = MyModel()\n    return model",
        })
        assert resp.status_code == 201

        # Step 2: List artifacts
        artifacts_resp = client.get(f"/api/artifacts/meeting/{meeting['id']}").json()
        assert artifacts_resp["total"] == 2

        # Step 3: Export as ZIP
        resp = client.get(f"/api/export/meeting/{meeting['id']}/zip")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            names = zf.namelist()
            assert any("model.py" in n for n in names)
            assert any("train.py" in n for n in names)
            assert any("README.md" in n for n in names)

        # Step 4: Export as Colab notebook
        resp = client.get(f"/api/export/meeting/{meeting['id']}/notebook")
        assert resp.status_code == 200
        notebook = resp.json()
        assert notebook["nbformat"] == 4
        code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
        assert len(code_cells) == 2

        # Step 5: Export as GitHub files
        resp = client.get(f"/api/export/meeting/{meeting['id']}/github")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_name"] == "Code Generation"
        assert len(data["files"]) == 3  # README + 2 artifacts

    def test_agent_update_and_position_save(self, client):
        """Frontend flow: Visual editor -> drag agent -> save position."""
        team = client.post("/api/teams/", json={"name": "Editor Team"}).json()
        agent = client.post("/api/agents/", json={
            "team_id": team["id"],
            "name": "Agent A",
            "title": "Researcher",
            "expertise": "AI",
            "goal": "Research",
            "role": "Lead",
            "model": "gpt-4",
        }).json()

        # Default positions
        assert agent["position_x"] == 0.0
        assert agent["position_y"] == 0.0

        # Frontend: drag node in React Flow -> onNodeDragStop -> PUT position
        updated = client.put(f"/api/agents/{agent['id']}", json={
            "position_x": 250.5,
            "position_y": 100.3,
        }).json()
        assert updated["position_x"] == 250.5
        assert updated["position_y"] == 100.3

        # Frontend: edit system prompt in Monaco Editor -> save
        updated = client.put(f"/api/agents/{agent['id']}", json={
            "expertise": "Machine learning and NLP",
        }).json()
        assert "Machine learning and NLP" in updated["system_prompt"]
        # Position preserved
        assert updated["position_x"] == 250.5

    def test_onboarding_to_team_creation(self, client):
        """Frontend flow: Onboarding chat -> generate team -> verify."""
        # Step 1: Problem stage
        resp = client.post("/api/onboarding/chat", json={
            "message": "I want to study protein-drug interactions",
            "stage": "problem",
            "context": {},
        })
        assert resp.status_code == 200
        chat_resp = resp.json()
        assert "data" in chat_resp
        assert chat_resp["data"]["domain"]  # Should have detected a domain

        # Step 2: Generate team from onboarding result
        resp = client.post("/api/onboarding/generate-team", json={
            "team_name": "Drug Discovery Lab",
            "agents": [
                {
                    "name": "Dr. Pharma",
                    "title": "Pharmacologist",
                    "expertise": "Drug-target interactions",
                    "goal": "Identify drug candidates",
                    "role": "Lead pharmacology analysis",
                    "model": "gpt-4",
                },
                {
                    "name": "Dr. Protein",
                    "title": "Protein Scientist",
                    "expertise": "Protein structure and function",
                    "goal": "Analyze binding sites",
                    "role": "Structural analysis specialist",
                    "model": "claude-3-opus",
                },
            ],
        })
        assert resp.status_code == 201
        result = resp.json()
        assert result["name"] == "Drug Discovery Lab"
        assert len(result["agents"]) == 2

        # Verify the team is accessible via normal API
        team_detail = client.get(f"/api/teams/{result['id']}").json()
        assert len(team_detail["agents"]) == 2

    def test_api_key_management(self, client):
        """Frontend flow: Settings page -> add/list/delete API keys."""
        # Step 1: Add API key (returns 201)
        resp = client.post("/api/llm/api-keys", json={
            "provider": "openai",
            "api_key": "sk-test-key-12345678",
        })
        assert resp.status_code == 201
        key = resp.json()
        assert key["provider"] == "openai"
        assert key["key_preview"] == "...5678"

        # Step 2: List API keys
        keys = client.get("/api/llm/api-keys").json()
        assert len(keys) == 1
        # Should NOT expose the full key
        assert "encrypted_key" not in keys[0]
        assert "api_key" not in keys[0]

        # Step 3: Delete API key
        resp = client.delete(f"/api/llm/api-keys/{key['id']}")
        assert resp.status_code == 204

        # Verify deleted
        keys = client.get("/api/llm/api-keys").json()
        assert len(keys) == 0

    def test_code_extraction_from_meeting(self, client):
        """Frontend flow: Meeting with code -> extract artifacts."""
        team = client.post("/api/teams/", json={"name": "Extract Team"}).json()
        resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Code Discussion",
        })
        assert resp.status_code == 201
        meeting = resp.json()

        # Simulate agent message with code blocks
        resp = client.post(f"/api/meetings/{meeting['id']}/message", json={
            "content": "Here's the implementation:\n\n```python\nclass DataLoader:\n    def __init__(self, path):\n        self.path = path\n    \n    def load(self):\n        return open(self.path).read()\n```\n\nAnd the test:\n\n```python\ndef test_loader():\n    loader = DataLoader('test.txt')\n    assert loader.path == 'test.txt'\n```",
        })
        assert resp.status_code == 201

        # Extract code artifacts (returns 201)
        resp = client.post(f"/api/artifacts/meeting/{meeting['id']}/extract")
        assert resp.status_code == 201
        artifacts = resp.json()
        assert len(artifacts) == 2
        filenames = [a["filename"] for a in artifacts]
        assert "data_loader.py" in filenames  # From class DataLoader
        assert "test_loader.py" in filenames  # From def test_loader

    def test_cascade_delete_cleanup(self, client):
        """Verify deleting a team cleans up all related data."""
        # Create full data tree
        team = client.post("/api/teams/", json={"name": "Temp Team"}).json()
        client.post("/api/agents/", json={
            "team_id": team["id"],
            "name": "Agent",
            "title": "T",
            "expertise": "E",
            "goal": "G",
            "role": "R",
            "model": "gpt-4",
        })
        resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Temp Meeting",
        })
        meeting = resp.json()
        client.post("/api/artifacts/", json={
            "meeting_id": meeting["id"],
            "filename": "temp.py",
            "language": "python",
            "content": "pass",
        })

        # Delete team
        resp = client.delete(f"/api/teams/{team['id']}")
        assert resp.status_code == 204

        # Verify team is gone
        assert client.get(f"/api/teams/{team['id']}").status_code == 404

        # Verify meeting is also gone (cascade)
        assert client.get(f"/api/meetings/{meeting['id']}").status_code == 404

    def test_error_handling_consistency(self, client):
        """Verify consistent error responses across all APIs."""
        # 404s return proper JSON with detail field
        endpoints_404 = [
            "/api/teams/nonexistent",
            "/api/agents/nonexistent",
            "/api/meetings/nonexistent",
            "/api/artifacts/nonexistent",
            "/api/export/meeting/nonexistent/zip",
        ]
        for endpoint in endpoints_404:
            resp = client.get(endpoint)
            assert resp.status_code == 404, f"Expected 404 for {endpoint}"
            body = resp.json()
            assert "detail" in body, f"Missing 'detail' in 404 response for {endpoint}"

        # 422s for invalid data
        resp = client.post("/api/teams/", json={})  # Missing required 'name'
        assert resp.status_code == 422
