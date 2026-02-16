"""Tests for Export Functionality (Step 1.9 + V12 enhancements).

Covers:
- Exporter: ZIP, Colab notebook, GitHub files
- Subdirectory support in ZIP/GitHub exports
- Requirements.txt auto-generation
- Directory tree in README
- Colab path annotations
- JSON export endpoint
- Export API: ZIP download, notebook download, GitHub format, JSON export
"""

import json
import zipfile
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.exporter import (
    export_as_zip,
    export_as_colab_notebook,
    export_as_github_files,
    _build_directory_tree,
)


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

    def test_export_zip_readme_has_tree(self):
        """ZIP includes README with directory tree structure."""
        zip_bytes = export_as_zip(self.SAMPLE_ARTIFACTS, "my_project")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            readme = zf.read("my_project/README.md").decode()
            assert "Project Structure" in readme
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
        paths = [f["path"] for f in files]
        assert "README.md" in paths
        assert "main.py" in paths
        assert "utils.py" in paths

    def test_export_github_readme_content(self):
        """GitHub README has directory tree structure."""
        files = export_as_github_files(self.SAMPLE_ARTIFACTS, "my_repo")
        readme = next(f for f in files if f["path"] == "README.md")
        assert "main.py" in readme["content"]
        assert "my_repo" in readme["content"]
        assert "Project Structure" in readme["content"]


class TestSubdirectoryExport:
    """Tests for subdirectory support in exports."""

    SUBDIR_ARTIFACTS = [
        {"filename": "src/models/pipeline.py", "language": "python",
         "content": "import numpy\nclass Pipeline:\n    pass", "description": "ML pipeline"},
        {"filename": "src/utils.py", "language": "python",
         "content": "import pandas\ndef load():\n    pass", "description": "Utils"},
        {"filename": "tests/test_pipeline.py", "language": "python",
         "content": "import pytest\ndef test_it():\n    pass", "description": "Tests"},
    ]

    def test_zip_subdirectories(self):
        """ZIP preserves subdirectory structure."""
        zip_bytes = export_as_zip(self.SUBDIR_ARTIFACTS, "proj")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "proj/src/models/pipeline.py" in names
            assert "proj/src/utils.py" in names
            assert "proj/tests/test_pipeline.py" in names

    def test_zip_requirements_generated(self):
        """ZIP includes auto-generated requirements.txt."""
        zip_bytes = export_as_zip(self.SUBDIR_ARTIFACTS, "proj")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "proj/requirements.txt" in names
            reqs = zf.read("proj/requirements.txt").decode()
            assert "numpy" in reqs
            assert "pandas" in reqs

    def test_zip_readme_directory_tree(self):
        """ZIP README shows directory tree."""
        zip_bytes = export_as_zip(self.SUBDIR_ARTIFACTS, "proj")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            readme = zf.read("proj/README.md").decode()
            assert "src/" in readme
            assert "tests/" in readme

    def test_github_subdirectory_paths(self):
        """GitHub export preserves subdirectory paths."""
        files = export_as_github_files(self.SUBDIR_ARTIFACTS, "repo")
        paths = [f["path"] for f in files]
        assert "src/models/pipeline.py" in paths
        assert "src/utils.py" in paths
        assert "tests/test_pipeline.py" in paths
        assert "requirements.txt" in paths

    def test_colab_path_annotations(self):
        """Colab notebook includes path annotations for subdirectory files."""
        notebook = export_as_colab_notebook(self.SUBDIR_ARTIFACTS, "proj")
        md_cells = [c for c in notebook["cells"] if c["cell_type"] == "markdown"]
        # Find markdown cell with target path annotation
        path_annotations = [
            c for c in md_cells
            if any("Target path" in line for line in c["source"])
        ]
        assert len(path_annotations) > 0

    def test_colab_pip_install_cell(self):
        """Colab notebook includes pip install cell for requirements."""
        notebook = export_as_colab_notebook(self.SUBDIR_ARTIFACTS, "proj")
        code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
        pip_cells = [c for c in code_cells if any("!pip install" in s for s in c["source"])]
        assert len(pip_cells) == 1
        pip_content = "".join(pip_cells[0]["source"])
        assert "numpy" in pip_content


class TestDirectoryTree:
    """Tests for _build_directory_tree helper."""

    def test_flat_files(self):
        """Flat file list renders correctly."""
        tree = _build_directory_tree(["main.py", "utils.py"])
        assert "main.py" in tree
        assert "utils.py" in tree

    def test_nested_directories(self):
        """Nested directory structure renders correctly."""
        tree = _build_directory_tree(["src/models/a.py", "src/utils.py", "tests/test.py"])
        assert "src/" in tree
        assert "models/" in tree
        assert "tests/" in tree


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
        assert len(data["files"]) >= 3  # README + 2 artifacts (+ possible requirements.txt)

    def test_export_json(self, client, meeting_with_artifacts):
        """Export meeting data as JSON."""
        # Add a message so we have a summary
        client.post(f"/api/meetings/{meeting_with_artifacts['id']}/message", json={
            "content": "The final answer is 42.",
        })

        resp = client.get(f"/api/export/meeting/{meeting_with_artifacts['id']}/json")
        assert resp.status_code == 200
        data = resp.json()
        assert "meeting" in data
        assert "team" in data
        assert "agents" in data
        assert "messages" in data
        assert "artifacts" in data
        assert "summary" in data
        assert data["meeting"]["title"] == "Export Test"
        assert len(data["artifacts"]) == 2

    def test_export_json_not_found(self, client):
        """JSON export for nonexistent meeting returns 404."""
        resp = client.get("/api/export/meeting/nonexistent/json")
        assert resp.status_code == 404

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

    def test_export_paper(self, client, meeting_with_artifacts):
        """Paper export returns JSON with content and title; download=1 returns markdown."""
        resp = client.get(f"/api/export/meeting/{meeting_with_artifacts['id']}/paper")
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "title" in data
        assert "Abstract" in data["content"] or "Discussion" in data["content"]

        resp_dl = client.get(f"/api/export/meeting/{meeting_with_artifacts['id']}/paper?download=1")
        assert resp_dl.status_code == 200
        assert "text/markdown" in resp_dl.headers.get("content-type", "")

    def test_export_blog(self, client, meeting_with_artifacts):
        """Blog export returns JSON with content and title; download=1 returns markdown."""
        resp = client.get(f"/api/export/meeting/{meeting_with_artifacts['id']}/blog")
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "title" in data

        resp_dl = client.get(f"/api/export/meeting/{meeting_with_artifacts['id']}/blog?download=1")
        assert resp_dl.status_code == 200
        assert "text/markdown" in resp_dl.headers.get("content-type", "")
