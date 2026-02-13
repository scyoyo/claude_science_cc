"""Tests for input validation, edge cases, and sanitization."""

import pytest
from app.core.sanitize import sanitize_text, strip_html_tags


class TestSanitization:
    def test_strip_html_tags(self):
        assert strip_html_tags("<b>bold</b>") == "bold"
        assert strip_html_tags("<script>alert(1)</script>") == "alert(1)"
        assert strip_html_tags("no tags") == "no tags"

    def test_sanitize_script_patterns(self):
        assert "javascript:" not in sanitize_text("javascript:alert(1)")
        assert "onclick" not in sanitize_text('onclick="alert(1)"')
        assert "<script" not in sanitize_text("<script>alert(1)</script>")

    def test_sanitize_normal_text(self):
        text = "Hello, this is a normal research description."
        assert sanitize_text(text) == text

    def test_sanitize_preserves_markdown(self):
        text = "# Heading\n- bullet\n**bold** and *italic*"
        assert sanitize_text(text) == text


class TestTeamValidation:
    def test_create_team_empty_name(self, client):
        """Team name cannot be empty."""
        resp = client.post("/api/teams/", json={"name": ""})
        assert resp.status_code == 422

    def test_create_team_long_name(self, client):
        """Team name has reasonable limits."""
        resp = client.post("/api/teams/", json={"name": "x" * 256})
        # Should either succeed (if no max length) or fail with 422
        assert resp.status_code in (201, 422)

    def test_create_team_special_characters(self, client):
        """Team name with special characters works."""
        resp = client.post("/api/teams/", json={"name": "Team (α-β) Test #1"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "Team (α-β) Test #1"

    def test_create_team_unicode(self, client):
        """Team name supports unicode."""
        resp = client.post("/api/teams/", json={"name": "团队 チーム 팀"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "团队 チーム 팀"


class TestAgentValidation:
    def _agent_data(self, team_id, **overrides):
        data = {
            "team_id": team_id,
            "name": "Agent",
            "title": "Scientist",
            "expertise": "ML",
            "goal": "Research",
            "role": "Researcher",
            "model": "gpt-4",
        }
        data.update(overrides)
        return data

    def test_create_agent_empty_name(self, client):
        """Agent name cannot be empty."""
        team = client.post("/api/teams/", json={"name": "T"}).json()
        resp = client.post("/api/agents/", json=self._agent_data(team["id"], name=""))
        assert resp.status_code == 422

    def test_create_agent_empty_model(self, client):
        """Agent model cannot be empty."""
        team = client.post("/api/teams/", json={"name": "T"}).json()
        resp = client.post("/api/agents/", json=self._agent_data(team["id"], model=""))
        assert resp.status_code == 422

    def test_create_agent_invalid_team_id(self, client):
        """Non-existent team ID returns 404."""
        resp = client.post("/api/agents/", json=self._agent_data("nonexistent"))
        assert resp.status_code == 404


class TestMeetingValidation:
    def test_create_meeting_empty_title(self, client):
        """Meeting title cannot be empty."""
        team = client.post("/api/teams/", json={"name": "T"}).json()
        resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "",
        })
        assert resp.status_code == 422

    def test_create_meeting_max_rounds_limit(self, client):
        """Max rounds has upper limit of 20."""
        team = client.post("/api/teams/", json={"name": "T"}).json()
        resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Test",
            "max_rounds": 100,
        })
        assert resp.status_code == 422

    def test_create_meeting_zero_rounds(self, client):
        """Max rounds must be at least 1."""
        team = client.post("/api/teams/", json={"name": "T"}).json()
        resp = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Test",
            "max_rounds": 0,
        })
        assert resp.status_code == 422


class TestSearchValidation:
    def test_search_empty_query(self, client):
        """Search query cannot be empty."""
        resp = client.get("/api/search/teams", params={"q": ""})
        assert resp.status_code == 422

    def test_search_pagination_negative_skip(self, client):
        """Negative skip is rejected."""
        resp = client.get("/api/search/teams", params={"q": "test", "skip": -1})
        assert resp.status_code == 422

    def test_search_pagination_zero_limit(self, client):
        """Zero limit is rejected."""
        resp = client.get("/api/search/teams", params={"q": "test", "limit": 0})
        assert resp.status_code == 422

    def test_search_pagination_excessive_limit(self, client):
        """Excessive limit is capped."""
        resp = client.get("/api/search/teams", params={"q": "test", "limit": 999})
        assert resp.status_code == 422


class TestSQLInjectionPrevention:
    def test_team_name_sql_injection(self, client):
        """SQL injection in team name is treated as plain text."""
        resp = client.post("/api/teams/", json={
            "name": "'; DROP TABLE teams; --"
        })
        assert resp.status_code == 201
        # Verify the team was created with literal text
        team_id = resp.json()["id"]
        get_resp = client.get(f"/api/teams/{team_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "'; DROP TABLE teams; --"

    def test_search_sql_injection(self, client):
        """SQL injection in search query doesn't cause errors."""
        resp = client.get("/api/search/teams", params={"q": "' OR 1=1; --"})
        assert resp.status_code == 200

    def test_path_traversal_in_id(self, client):
        """Path traversal attempts in IDs return 404."""
        resp = client.get("/api/teams/../../../etc/passwd")
        assert resp.status_code in (404, 422)
