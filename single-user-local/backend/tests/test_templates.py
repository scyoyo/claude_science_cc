import pytest


class TestTemplates:
    def test_list_all_templates(self, client):
        """List all available templates."""
        resp = client.get("/api/templates/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 10
        # Verify template structure
        t = data[0]
        assert "id" in t
        assert "name" in t
        assert "title" in t
        assert "expertise" in t
        assert "goal" in t
        assert "role" in t
        assert "category" in t

    def test_filter_by_category(self, client):
        """Filter templates by category."""
        resp = client.get("/api/templates/", params={"category": "AI/ML"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        for t in data:
            assert t["category"] == "AI/ML"

    def test_filter_by_category_case_insensitive(self, client):
        """Category filter is case-insensitive."""
        resp = client.get("/api/templates/", params={"category": "general"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        for t in data:
            assert t["category"] == "General"

    def test_get_template_by_id(self, client):
        """Get a specific template."""
        resp = client.get("/api/templates/ml-researcher")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ml-researcher"
        assert data["name"] == "ML Researcher"

    def test_get_template_not_found(self, client):
        """Get nonexistent template returns 404."""
        resp = client.get("/api/templates/nonexistent")
        assert resp.status_code == 404

    def test_apply_template(self, client):
        """Create agent from template."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        resp = client.post(
            "/api/templates/apply",
            params={"template_id": "ml-researcher", "team_id": team["id"]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "ML Researcher"
        assert data["team_id"] == team["id"]
        assert "system_prompt" in data
        assert data["model"] == "gpt-4"

    def test_apply_template_invalid_template(self, client):
        """Apply nonexistent template returns 404."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        resp = client.post(
            "/api/templates/apply",
            params={"template_id": "fake", "team_id": team["id"]},
        )
        assert resp.status_code == 404

    def test_apply_template_invalid_team(self, client):
        """Apply template to nonexistent team returns 404."""
        resp = client.post(
            "/api/templates/apply",
            params={"template_id": "ml-researcher", "team_id": "fake-team"},
        )
        assert resp.status_code == 404
