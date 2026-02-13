"""Tests for Code Generation / Artifacts (Step 1.8).

Covers:
- CodeExtractor: code block extraction, filename suggestion, multi-message extraction
- Artifact API: CRUD, auto-extraction from meeting messages
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.code_extractor import extract_code_blocks, extract_from_meeting_messages


# ==================== CodeExtractor Unit Tests ====================


class TestCodeExtractor:
    """Tests for code block extraction."""

    def test_extract_python_block(self):
        """Extract a Python code block."""
        text = 'Here is the code:\n```python\ndef hello():\n    print("Hello")\n```\nDone.'
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert "def hello" in blocks[0].content
        assert blocks[0].suggested_filename.endswith(".py")

    def test_extract_multiple_blocks(self):
        """Extract multiple code blocks."""
        text = (
            "```python\nclass Foo:\n    pass\n```\n\n"
            "And also:\n```javascript\nfunction bar() {}\n```"
        )
        blocks = extract_code_blocks(text)
        assert len(blocks) == 2
        assert blocks[0].language == "python"
        assert blocks[1].language == "javascript"

    def test_extract_with_no_language(self):
        """Code block without language tag defaults to 'text'."""
        text = "```\nsome code\n```"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].language == "text"
        assert blocks[0].suggested_filename.endswith(".txt")

    def test_extract_empty_block_skipped(self):
        """Empty code blocks are skipped."""
        text = "```python\n\n```"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 0

    def test_suggest_filename_from_class(self):
        """Filename suggested from Python class name."""
        text = "```python\nclass DataProcessor:\n    pass\n```"
        blocks = extract_code_blocks(text)
        assert blocks[0].suggested_filename == "data_processor.py"

    def test_suggest_filename_from_function(self):
        """Filename suggested from Python function name."""
        text = "```python\ndef process_data():\n    pass\n```"
        blocks = extract_code_blocks(text)
        assert blocks[0].suggested_filename == "process_data.py"

    def test_suggest_filename_fallback(self):
        """Fallback filename when no class/function found."""
        text = "```python\nx = 42\n```"
        blocks = extract_code_blocks(text)
        assert blocks[0].suggested_filename == "code_1.py"

    def test_source_agent_attribution(self):
        """Source agent is attributed."""
        text = "```python\nprint('hello')\n```"
        blocks = extract_code_blocks(text, source_agent="Dr. Smith")
        assert blocks[0].source_agent == "Dr. Smith"

    def test_no_code_blocks(self):
        """No code blocks returns empty list."""
        text = "This is just text without any code."
        blocks = extract_code_blocks(text)
        assert len(blocks) == 0

    def test_extract_from_meeting_messages(self):
        """Extract code from multiple meeting messages."""
        messages = [
            {"content": "Let me write the code:\n```python\ndef solve():\n    pass\n```",
             "agent_name": "ML Lead", "role": "assistant"},
            {"content": "What about approach B?",
             "agent_name": None, "role": "user"},
            {"content": "```javascript\nconst x = 1;\n```",
             "agent_name": "Data Engineer", "role": "assistant"},
        ]
        blocks = extract_from_meeting_messages(messages)
        assert len(blocks) == 2
        assert blocks[0].source_agent == "ML Lead"
        assert blocks[1].source_agent == "Data Engineer"


# ==================== Artifact API Tests ====================


class TestArtifactAPI:
    """Tests for artifact CRUD endpoints."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def meeting(self, client):
        """Create a team and meeting."""
        team = client.post("/api/teams/", json={"name": "Test Team"}).json()
        meeting = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Code Meeting",
        }).json()
        return meeting

    def test_create_artifact(self, client, meeting):
        """Create a code artifact."""
        resp = client.post("/api/artifacts/", json={
            "meeting_id": meeting["id"],
            "filename": "solution.py",
            "language": "python",
            "content": "def solve():\n    pass",
            "description": "Main solution",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "solution.py"
        assert data["language"] == "python"
        assert data["version"] == 1

    def test_create_artifact_invalid_meeting(self, client):
        """Creating artifact for nonexistent meeting fails."""
        resp = client.post("/api/artifacts/", json={
            "meeting_id": "nonexistent",
            "filename": "test.py",
            "content": "pass",
        })
        assert resp.status_code == 404

    def test_get_artifact(self, client, meeting):
        """Get a specific artifact."""
        create_resp = client.post("/api/artifacts/", json={
            "meeting_id": meeting["id"],
            "filename": "test.py",
            "content": "x = 1",
        })
        artifact_id = create_resp.json()["id"]

        resp = client.get(f"/api/artifacts/{artifact_id}")
        assert resp.status_code == 200
        assert resp.json()["filename"] == "test.py"

    def test_list_meeting_artifacts(self, client, meeting):
        """List artifacts for a meeting."""
        client.post("/api/artifacts/", json={
            "meeting_id": meeting["id"],
            "filename": "a.py",
            "content": "a = 1",
        })
        client.post("/api/artifacts/", json={
            "meeting_id": meeting["id"],
            "filename": "b.py",
            "content": "b = 2",
        })
        resp = client.get(f"/api/artifacts/meeting/{meeting['id']}")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_artifact(self, client, meeting):
        """Update artifact content bumps version."""
        create_resp = client.post("/api/artifacts/", json={
            "meeting_id": meeting["id"],
            "filename": "evolving.py",
            "content": "v1",
        })
        artifact_id = create_resp.json()["id"]

        resp = client.put(f"/api/artifacts/{artifact_id}", json={
            "content": "v2",
        })
        assert resp.status_code == 200
        assert resp.json()["version"] == 2
        assert resp.json()["content"] == "v2"

    def test_delete_artifact(self, client, meeting):
        """Delete an artifact."""
        create_resp = client.post("/api/artifacts/", json={
            "meeting_id": meeting["id"],
            "filename": "delete_me.py",
            "content": "x",
        })
        artifact_id = create_resp.json()["id"]

        resp = client.delete(f"/api/artifacts/{artifact_id}")
        assert resp.status_code == 204

        resp = client.get(f"/api/artifacts/{artifact_id}")
        assert resp.status_code == 404


class TestExtractEndpoint:
    """Tests for the auto-extract endpoint."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def meeting_with_messages(self, client):
        """Create a meeting with messages containing code."""
        team = client.post("/api/teams/", json={"name": "Code Team"}).json()
        for name in ["Coder"]:
            client.post("/api/agents/", json={
                "team_id": team["id"],
                "name": name,
                "title": "Dev",
                "expertise": "coding",
                "goal": "write code",
                "role": "developer",
                "model": "gpt-4",
            })
        meeting = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Code Session",
        }).json()

        # Add messages with code blocks
        client.post(f"/api/meetings/{meeting['id']}/message", json={
            "content": "Here is the solution:\n```python\nclass DataPipeline:\n    def run(self):\n        pass\n```\nAnd a helper:\n```python\ndef load_data():\n    return []\n```",
        })
        return meeting

    def test_extract_from_meeting(self, client, meeting_with_messages):
        """Auto-extract code from meeting messages."""
        resp = client.post(f"/api/artifacts/meeting/{meeting_with_messages['id']}/extract")
        assert resp.status_code == 201
        artifacts = resp.json()
        assert len(artifacts) == 2
        filenames = [a["filename"] for a in artifacts]
        assert "data_pipeline.py" in filenames
        assert "load_data.py" in filenames

    def test_extract_empty_meeting(self, client):
        """Extracting from meeting with no code returns empty."""
        team = client.post("/api/teams/", json={"name": "Empty Team"}).json()
        meeting = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "No Code",
        }).json()

        resp = client.post(f"/api/artifacts/meeting/{meeting['id']}/extract")
        assert resp.status_code == 201
        assert len(resp.json()) == 0

    def test_extract_nonexistent_meeting(self, client):
        """Extracting from nonexistent meeting returns 404."""
        resp = client.post("/api/artifacts/meeting/nonexistent/extract")
        assert resp.status_code == 404
