"""Tests for API versioning: /api/ and /api/v1/ both work."""

import pytest


class TestAPIVersioning:
    def test_teams_v1_prefix(self, client):
        """Teams endpoint works with /api/v1/ prefix."""
        resp = client.post("/api/v1/teams/", json={"name": "V1 Team"})
        assert resp.status_code == 201
        team = resp.json()
        assert team["name"] == "V1 Team"

        # List via v1
        resp = client.get("/api/v1/teams/")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_agents_v1_prefix(self, client):
        """Agents endpoint works with /api/v1/ prefix."""
        team = client.post("/api/v1/teams/", json={"name": "Team"}).json()
        resp = client.post("/api/v1/agents/", json={
            "team_id": team["id"],
            "name": "Agent",
            "title": "Sci",
            "expertise": "X",
            "goal": "Y",
            "role": "Z",
            "model": "gpt-4",
        })
        assert resp.status_code == 201

    def test_search_v1_prefix(self, client):
        """Search works with /api/v1/ prefix."""
        client.post("/api/teams/", json={"name": "Searchable Team"})
        resp = client.get("/api/v1/search/teams", params={"q": "Searchable"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_templates_v1_prefix(self, client):
        """Templates work with /api/v1/ prefix."""
        resp = client.get("/api/v1/templates/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 10

    def test_cross_prefix_compatibility(self, client):
        """Data created via /api/ is accessible via /api/v1/ and vice versa."""
        # Create via /api/
        team = client.post("/api/teams/", json={"name": "Cross Test"}).json()
        # Access via /api/v1/
        resp = client.get(f"/api/v1/teams/{team['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Cross Test"

    def test_version_header_present(self, client):
        """Responses include X-API-Version header."""
        resp = client.get("/")
        assert resp.headers.get("X-API-Version") == "v1"

    def test_version_header_on_api_response(self, client):
        """API responses include version header."""
        resp = client.get("/api/templates/")
        assert resp.headers.get("X-API-Version") == "v1"
