"""Tests for LLM-assisted code extraction.

Covers:
- LLMCodeExtractor: Smart code extraction with LLM assistance
- Project structure inference
- Intelligent file naming and organization
- Dependency analysis
- Smart extract API endpoint
"""

import json
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.llm_code_extractor import (
    LLMCodeExtractor,
    ProjectStructure,
    SmartExtractedCode,
    extract_with_llm,
)


# ==================== Mock LLM Function ====================


def make_mock_llm(responses):
    """Create a sync mock llm_call(system_prompt, messages) -> str."""
    responses_iter = iter(responses)

    def mock_call(system_prompt, messages):
        return next(responses_iter)

    return mock_call


# ==================== LLMCodeExtractor Unit Tests ====================


class TestProjectStructureAnalysis:
    """Tests for project structure inference."""

    @pytest.mark.asyncio
    async def test_analyze_web_app_structure(self):
        """Analyze a web app project."""
        messages = [
            {"content": "Let's build a Flask web application with user authentication.", "agent_name": "Lead", "role": "assistant"},
            {"content": "We'll need routes, models, and templates.", "agent_name": "Dev", "role": "assistant"},
        ]

        llm_response = json.dumps({
            "project_type": "web_app",
            "suggested_folders": ["app", "templates", "static", "tests"],
            "entry_point": "app/main.py",
            "readme_content": "# Flask Web App\n\nA web application with authentication.",
        })

        mock_llm = make_mock_llm([llm_response])
        extractor = LLMCodeExtractor(llm_call=mock_llm)

        structure = await extractor.analyze_project_structure(messages)

        assert structure.project_type == "web_app"
        assert "app" in structure.suggested_folders
        assert "templates" in structure.suggested_folders
        assert structure.entry_point == "app/main.py"
        assert "Flask" in structure.readme_content

    @pytest.mark.asyncio
    async def test_analyze_data_science_structure(self):
        """Analyze a data science project."""
        messages = [
            {"content": "Let's build a machine learning pipeline for image classification.", "agent_name": "ML Lead", "role": "assistant"},
            {"content": "We need data loading, preprocessing, and model training.", "agent_name": "Data Scientist", "role": "assistant"},
        ]

        llm_response = json.dumps({
            "project_type": "data_science",
            "suggested_folders": ["data", "notebooks", "src", "models", "tests"],
            "entry_point": "src/train.py",
            "readme_content": "# Image Classification Pipeline\n\nML project for image classification.",
        })

        mock_llm = make_mock_llm([llm_response])
        extractor = LLMCodeExtractor(llm_call=mock_llm)

        structure = await extractor.analyze_project_structure(messages)

        assert structure.project_type == "data_science"
        assert "notebooks" in structure.suggested_folders
        assert "models" in structure.suggested_folders
        assert structure.entry_point == "src/train.py"

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_json(self):
        """Fallback to basic structure if LLM returns invalid JSON."""
        messages = [{"content": "Some discussion", "agent_name": "Dev", "role": "assistant"}]

        mock_llm = make_mock_llm(["This is not JSON"])
        extractor = LLMCodeExtractor(llm_call=mock_llm)

        structure = await extractor.analyze_project_structure(messages)

        # Should have fallback values
        assert structure.project_type == "other"
        assert "src" in structure.suggested_folders
        assert "tests" in structure.suggested_folders


class TestSmartCodeExtraction:
    """Tests for intelligent code extraction."""

    @pytest.mark.asyncio
    async def test_extract_with_proper_paths(self):
        """Extract code with folder-organized paths."""
        messages = [
            {"content": "Here's the main app:\n```python\nfrom flask import Flask\napp = Flask(__name__)\n```", "agent_name": "Dev", "role": "assistant"},
            {"content": "And the user model:\n```python\nclass User:\n    def __init__(self, name):\n        self.name = name\n```", "agent_name": "Dev", "role": "assistant"},
        ]

        structure_response = json.dumps({
            "project_type": "web_app",
            "suggested_folders": ["app", "models", "tests"],
            "entry_point": "app/main.py",
            "readme_content": "# Web App",
        })

        code_response = json.dumps([
            {
                "filename": "app/main.py",
                "language": "python",
                "content": "from flask import Flask\napp = Flask(__name__)",
                "description": "Main Flask application entry point",
                "dependencies": ["flask"],
                "related_files": ["models/user.py"],
            },
            {
                "filename": "models/user.py",
                "language": "python",
                "content": "class User:\n    def __init__(self, name):\n        self.name = name",
                "description": "User model class",
                "dependencies": [],
                "related_files": [],
            },
        ])

        mock_llm = make_mock_llm([structure_response, code_response])
        extractor = LLMCodeExtractor(llm_call=mock_llm)

        code_files = await extractor.extract_code_smart(messages)

        assert len(code_files) == 2
        assert code_files[0].filename == "app/main.py"
        assert code_files[1].filename == "models/user.py"
        assert "flask" in code_files[0].dependencies
        assert code_files[0].description == "Main Flask application entry point"

    @pytest.mark.asyncio
    async def test_extract_without_markdown_blocks(self):
        """LLM can extract code even without markdown blocks."""
        messages = [
            {"content": "The function is: def hello(): return 'hi'", "agent_name": "Dev", "role": "assistant"},
        ]

        structure_response = json.dumps({
            "project_type": "other",
            "suggested_folders": ["src"],
            "entry_point": None,
            "readme_content": None,
        })

        code_response = json.dumps([
            {
                "filename": "src/hello.py",
                "language": "python",
                "content": "def hello():\n    return 'hi'",
                "description": "Simple hello function",
                "dependencies": [],
                "related_files": [],
            },
        ])

        mock_llm = make_mock_llm([structure_response, code_response])
        extractor = LLMCodeExtractor(llm_call=mock_llm)

        code_files = await extractor.extract_code_smart(messages)

        assert len(code_files) == 1
        assert "def hello" in code_files[0].content

    @pytest.mark.asyncio
    async def test_extract_groups_related_code(self):
        """LLM groups related code snippets into single files."""
        messages = [
            {"content": "First, the base class:\n```python\nclass Animal:\n    pass\n```", "agent_name": "Dev", "role": "assistant"},
            {"content": "Then subclasses:\n```python\nclass Dog(Animal):\n    pass\nclass Cat(Animal):\n    pass\n```", "agent_name": "Dev", "role": "assistant"},
        ]

        structure_response = json.dumps({
            "project_type": "library",
            "suggested_folders": ["src"],
            "entry_point": None,
            "readme_content": None,
        })

        # LLM intelligently merges related classes into one file
        code_response = json.dumps([
            {
                "filename": "src/animals.py",
                "language": "python",
                "content": "class Animal:\n    pass\n\nclass Dog(Animal):\n    pass\n\nclass Cat(Animal):\n    pass",
                "description": "Animal class hierarchy",
                "dependencies": [],
                "related_files": [],
            },
        ])

        mock_llm = make_mock_llm([structure_response, code_response])
        extractor = LLMCodeExtractor(llm_call=mock_llm)

        code_files = await extractor.extract_code_smart(messages)

        assert len(code_files) == 1
        assert "Animal" in code_files[0].content
        assert "Dog" in code_files[0].content
        assert "Cat" in code_files[0].content

    @pytest.mark.asyncio
    async def test_extract_empty_messages(self):
        """No code in messages returns empty list."""
        messages = [
            {"content": "Let's discuss the approach.", "agent_name": "Lead", "role": "assistant"},
        ]

        structure_response = json.dumps({
            "project_type": "other",
            "suggested_folders": ["src"],
            "entry_point": None,
            "readme_content": None,
        })

        code_response = json.dumps([])  # No code found

        mock_llm = make_mock_llm([structure_response, code_response])
        extractor = LLMCodeExtractor(llm_call=mock_llm)

        code_files = await extractor.extract_code_smart(messages)

        assert len(code_files) == 0

    @pytest.mark.asyncio
    async def test_source_agent_attribution(self):
        """Source agent is attributed when code is found in their message."""
        messages = [
            {"content": "Here's my solution:\n```python\ndef solve():\n    return 42\n```", "agent_name": "Alice", "role": "assistant"},
        ]

        structure_response = json.dumps({
            "project_type": "other",
            "suggested_folders": ["src"],
            "entry_point": None,
            "readme_content": None,
        })

        code_response = json.dumps([
            {
                "filename": "src/solution.py",
                "language": "python",
                "content": "def solve():\n    return 42",
                "description": "Solution function",
                "dependencies": [],
                "related_files": [],
            },
        ])

        mock_llm = make_mock_llm([structure_response, code_response])
        extractor = LLMCodeExtractor(llm_call=mock_llm)

        code_files = await extractor.extract_code_smart(messages)

        assert code_files[0].source_agent == "Alice"


class TestSmartRequirements:
    """Tests for LLM-assisted requirements generation."""

    @pytest.mark.asyncio
    async def test_generate_requirements_from_code(self):
        """Generate requirements.txt from Python code."""
        code_files = [
            SmartExtractedCode(
                filename="src/main.py",
                language="python",
                content="import numpy as np\nimport pandas as pd\nfrom sklearn.ensemble import RandomForestClassifier",
                description="Main script",
                dependencies=["numpy", "pandas", "scikit-learn"],
            ),
        ]

        llm_response = "numpy\npandas\nscikit-learn"
        mock_llm = make_mock_llm([llm_response])
        extractor = LLMCodeExtractor(llm_call=mock_llm)

        requirements = await extractor.generate_smart_requirements(code_files)

        assert "numpy" in requirements
        assert "pandas" in requirements
        assert "scikit-learn" in requirements

    @pytest.mark.asyncio
    async def test_requirements_with_versions(self):
        """LLM can include version constraints if mentioned."""
        code_files = [
            SmartExtractedCode(
                filename="src/app.py",
                language="python",
                content="# Requires Flask 2.0+\nimport flask",
                description="Flask app",
                dependencies=["flask"],
            ),
        ]

        llm_response = "flask>=2.0.0"
        mock_llm = make_mock_llm([llm_response])
        extractor = LLMCodeExtractor(llm_call=mock_llm)

        requirements = await extractor.generate_smart_requirements(code_files)

        assert "flask>=2.0.0" in requirements

    @pytest.mark.asyncio
    async def test_requirements_empty_for_non_python(self):
        """No requirements for non-Python code."""
        code_files = [
            SmartExtractedCode(
                filename="src/app.js",
                language="javascript",
                content="const x = 1;",
                description="JS file",
                dependencies=[],
            ),
        ]

        extractor = LLMCodeExtractor(llm_call=lambda s, m: "")

        requirements = await extractor.generate_smart_requirements(code_files)

        assert requirements == ""


class TestConvenienceFunction:
    """Tests for extract_with_llm convenience function."""

    @pytest.mark.asyncio
    async def test_extract_with_llm_convenience(self):
        """Convenience function returns both structure and code."""
        messages = [
            {"content": "```python\nprint('hello')\n```", "agent_name": "Dev", "role": "assistant"},
        ]

        structure_response = json.dumps({
            "project_type": "cli_tool",
            "suggested_folders": ["src"],
            "entry_point": "src/main.py",
            "readme_content": "# CLI Tool",
        })

        code_response = json.dumps([
            {
                "filename": "src/main.py",
                "language": "python",
                "content": "print('hello')",
                "description": "Main script",
                "dependencies": [],
                "related_files": [],
            },
        ])

        mock_llm = make_mock_llm([structure_response, code_response])

        code_files, structure = await extract_with_llm(messages, llm_call=mock_llm)

        assert structure.project_type == "cli_tool"
        assert len(code_files) == 1
        assert code_files[0].filename == "src/main.py"


# ==================== Smart Extract API Tests ====================


class TestSmartExtractAPI:
    """Tests for /extract-smart endpoint."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def meeting_with_code(self, client):
        """Create a meeting with code in messages."""
        team = client.post("/api/teams/", json={"name": "Dev Team"}).json()
        meeting = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Code Session",
        }).json()

        # Add message with code
        client.post(f"/api/meetings/{meeting['id']}/message", json={
            "content": "Here's a Flask app:\n```python\nfrom flask import Flask\napp = Flask(__name__)\n\n@app.route('/')\ndef home():\n    return 'Hello'\n```",
        })

        return meeting

    @pytest.mark.asyncio
    async def test_smart_extract_endpoint(self, client, meeting_with_code, monkeypatch):
        """Smart extract endpoint returns organized project structure."""
        # Mock the LLM extractor
        async def mock_analyze_structure(self, messages):
            return ProjectStructure(
                project_type="web_app",
                suggested_folders=["app", "tests"],
                entry_point="app/main.py",
                readme_content="# Flask App\n\nA simple web app.",
            )

        async def mock_extract_smart(self, messages, structure=None):
            return [
                SmartExtractedCode(
                    filename="app/main.py",
                    language="python",
                    content="from flask import Flask\napp = Flask(__name__)\n\n@app.route('/')\ndef home():\n    return 'Hello'",
                    description="Main Flask application",
                    dependencies=["flask"],
                    source_agent=None,
                    related_files=[],
                ),
            ]

        async def mock_generate_requirements(self, code_files):
            return "flask>=2.0.0"

        monkeypatch.setattr(LLMCodeExtractor, "analyze_project_structure", mock_analyze_structure)
        monkeypatch.setattr(LLMCodeExtractor, "extract_code_smart", mock_extract_smart)
        monkeypatch.setattr(LLMCodeExtractor, "generate_smart_requirements", mock_generate_requirements)

        # Call endpoint
        resp = client.post(f"/api/artifacts/meeting/{meeting_with_code['id']}/extract-smart")

        assert resp.status_code == 201
        data = resp.json()

        # Check project structure
        assert data["project_type"] == "web_app"
        assert "app" in data["suggested_folders"]
        assert data["entry_point"] == "app/main.py"
        assert "Flask App" in data["readme_content"]

        # Check extracted files
        assert len(data["files"]) == 1
        assert data["files"][0]["filename"] == "app/main.py"
        assert "flask" in data["files"][0]["dependencies"]

        # Check requirements
        assert "flask" in data["requirements_txt"]

    def test_smart_extract_nonexistent_meeting(self, client):
        """Smart extract on nonexistent meeting returns 404."""
        resp = client.post("/api/artifacts/meeting/nonexistent/extract-smart")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_smart_extract_saves_artifacts(self, client, meeting_with_code, monkeypatch):
        """Smart extract saves artifacts to database."""
        async def mock_analyze_structure(self, messages):
            return ProjectStructure(
                project_type="cli_tool",
                suggested_folders=["src"],
                entry_point="src/main.py",
                readme_content="# CLI Tool",
            )

        async def mock_extract_smart(self, messages, structure=None):
            return [
                SmartExtractedCode(
                    filename="src/main.py",
                    language="python",
                    content="print('hello')",
                    description="Main script",
                    dependencies=[],
                ),
            ]

        async def mock_generate_requirements(self, code_files):
            return ""

        monkeypatch.setattr(LLMCodeExtractor, "analyze_project_structure", mock_analyze_structure)
        monkeypatch.setattr(LLMCodeExtractor, "extract_code_smart", mock_extract_smart)
        monkeypatch.setattr(LLMCodeExtractor, "generate_smart_requirements", mock_generate_requirements)

        # Extract
        resp = client.post(f"/api/artifacts/meeting/{meeting_with_code['id']}/extract-smart")
        assert resp.status_code == 201

        # Verify artifacts were saved
        artifacts_resp = client.get(f"/api/artifacts/meeting/{meeting_with_code['id']}")
        artifacts = artifacts_resp.json()

        # Should have: code file + README
        assert artifacts["total"] == 2
        filenames = [a["filename"] for a in artifacts["items"]]
        assert "src/main.py" in filenames
        assert "README.md" in filenames
