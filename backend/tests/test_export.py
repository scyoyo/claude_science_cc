"""Tests for Export Functionality (Step 1.9).

Covers:
- Exporter: ZIP, Colab notebook, GitHub files
- Export API: ZIP download, notebook download, GitHub format
"""

import json
import zipfile
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.exporter import export_as_zip, export_as_colab_notebook, export_as_github_files


# ==================== Exporter Unit Tests ====================


class TestExporter:
    """Tests for export utility functions."""

    SAMPLE_ARTIFACTS = [
        {"filename": "main.py", "language": "python", "content": "print('hello')", "description": "Entry point"},
        {"filename": "utils.py", "language": "python", "content": "def helper():\n    pass", "description": "Helpers"},
    ]

    def test_export_zip(self):
        """Export as ZIP produces valid zip file."""
        zip_bytes = export_as_zip(self.SAMPLE_ARTIFACTS, "test_project")
        assert len(zip_bytes) > 0

        # Verify ZIP contents
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "test_project/README.md" in names
            assert "test_project/main.py" in names
            assert "test_project/utils.py" in names

            # Verify content
            content = zf.read("test_project/main.py").decode()
            assert content == "print('hello')"

    def test_export_zip_readme(self):
        """ZIP includes README with file listing."""
        zip_bytes = export_as_zip(self.SAMPLE_ARTIFACTS, "my_project")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            readme = zf.read("my_project/README.md").decode()
            assert "main.py" in readme
            assert "utils.py" in readme

    def test_export_colab_notebook(self):
        """Export as Colab notebook produces valid ipynb structure."""
        notebook = export_as_colab_notebook(self.SAMPLE_ARTIFACTS, "Test Notebook")
        assert notebook["nbformat"] == 4
        assert "cells" in notebook
        # Title + (desc + code) * 2 = 5 cells
        assert len(notebook["cells"]) == 5
        assert notebook["cells"][0]["cell_type"] == "markdown"
        assert "Test Notebook" in notebook["cells"][0]["source"][0]

    def test_export_colab_code_cells(self):
        """Colab notebook has correct code cells."""
        notebook = export_as_colab_notebook(self.SAMPLE_ARTIFACTS)
        code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
        assert len(code_cells) == 2
        # First code cell should contain main.py content
        assert any("hello" in "".join(c["source"]) for c in code_cells)

    def test_export_github_files(self):
        """Export as GitHub files produces correct structure."""
        files = export_as_github_files(self.SAMPLE_ARTIFACTS, "my_repo")
        assert len(files) == 3  # README + 2 artifacts
        paths = [f["path"] for f in files]
        assert "README.md" in paths
        assert "main.py" in paths
        assert "utils.py" in paths

    def test_export_github_readme_content(self):
        """GitHub README lists all files."""
        files = export_as_github_files(self.SAMPLE_ARTIFACTS, "my_repo")
        readme = next(f for f in files if f["path"] == "README.md")
        assert "main.py" in readme["content"]
        assert "my_repo" in readme["content"]


# ==================== Export API Tests ====================


class TestExportAPI:
    """Tests for export API endpoints."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def meeting_with_artifacts(self, client):
        """Create a meeting with code artifacts."""
        team = client.post("/api/teams/", json={"name": "Export Team"}).json()
        meeting = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Export Test",
        }).json()

        # Add artifacts
        client.post("/api/artifacts/", json={
            "meeting_id": meeting["id"],
            "filename": "solution.py",
            "language": "python",
            "content": "def solve():\n    return 42",
        })
        client.post("/api/artifacts/", json={
            "meeting_id": meeting["id"],
            "filename": "test_solution.py",
            "language": "python",
            "content": "assert solve() == 42",
        })
        return meeting

    def test_export_zip(self, client, meeting_with_artifacts):
        """Download ZIP file."""
        resp = client.get(f"/api/export/meeting/{meeting_with_artifacts['id']}/zip")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"

        # Verify it's a valid ZIP
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            names = zf.namelist()
            assert any("solution.py" in n for n in names)
            assert any("README.md" in n for n in names)

    def test_export_notebook(self, client, meeting_with_artifacts):
        """Download Colab notebook."""
        resp = client.get(f"/api/export/meeting/{meeting_with_artifacts['id']}/notebook")
        assert resp.status_code == 200

        notebook = resp.json()
        assert notebook["nbformat"] == 4
        assert len(notebook["cells"]) > 0

    def test_export_github(self, client, meeting_with_artifacts):
        """Get GitHub-ready files."""
        resp = client.get(f"/api/export/meeting/{meeting_with_artifacts['id']}/github")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_name"] == "Export Test"
        assert len(data["files"]) == 3  # README + 2 artifacts

    def test_export_empty_meeting_zip(self, client):
        """Export empty meeting fails."""
        team = client.post("/api/teams/", json={"name": "Empty"}).json()
        meeting = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Empty",
        }).json()

        resp = client.get(f"/api/export/meeting/{meeting['id']}/zip")
        assert resp.status_code == 400
        assert "No code artifacts" in resp.json()["detail"]

    def test_export_nonexistent_meeting(self, client):
        """Export nonexistent meeting returns 404."""
        resp = client.get("/api/export/meeting/nonexistent/zip")
        assert resp.status_code == 404
