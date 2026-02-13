import pytest


class TestSearchTeams:
    def test_search_by_name(self, client):
        """Search teams by name."""
        client.post("/api/teams/", json={"name": "Alpha Lab", "description": "Biology"})
        client.post("/api/teams/", json={"name": "Beta Lab", "description": "Physics"})
        client.post("/api/teams/", json={"name": "Gamma Group", "description": "Chemistry"})

        resp = client.get("/api/search/teams", params={"q": "Lab"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        names = [t["name"] for t in data["items"]]
        assert "Alpha Lab" in names
        assert "Beta Lab" in names

    def test_search_by_description(self, client):
        """Search teams by description."""
        client.post("/api/teams/", json={"name": "Team A", "description": "Machine learning research"})
        client.post("/api/teams/", json={"name": "Team B", "description": "Web development"})

        resp = client.get("/api/search/teams", params={"q": "learning"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "Team A"

    def test_search_case_insensitive(self, client):
        """Search is case-insensitive."""
        client.post("/api/teams/", json={"name": "DeepSeek Team"})

        resp = client.get("/api/search/teams", params={"q": "deepseek"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_search_no_results(self, client):
        """Search with no matching results."""
        client.post("/api/teams/", json={"name": "Test Team"})

        resp = client.get("/api/search/teams", params={"q": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    def test_search_pagination(self, client):
        """Search respects skip/limit pagination."""
        for i in range(5):
            client.post("/api/teams/", json={"name": f"Research Lab {i}"})

        resp = client.get("/api/search/teams", params={"q": "Research", "skip": 2, "limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["skip"] == 2
        assert data["limit"] == 2

    def test_search_requires_query(self, client):
        """Search requires q parameter."""
        resp = client.get("/api/search/teams")
        assert resp.status_code == 422


class TestSearchAgents:
    def _create_agent(self, client, team_id, **kwargs):
        defaults = {
            "team_id": team_id,
            "name": "Agent",
            "title": "Scientist",
            "expertise": "General",
            "goal": "Research",
            "role": "Researcher",
            "model": "gpt-4",
        }
        defaults.update(kwargs)
        return client.post("/api/agents/", json=defaults)

    def test_search_by_name(self, client):
        """Search agents by name."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        self._create_agent(client, team["id"], name="Alice the Biologist")
        self._create_agent(client, team["id"], name="Bob the Physicist")

        resp = client.get("/api/search/agents", params={"q": "Alice"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "Alice the Biologist"

    def test_search_by_expertise(self, client):
        """Search agents by expertise."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        self._create_agent(client, team["id"], name="A1", expertise="Machine Learning")
        self._create_agent(client, team["id"], name="A2", expertise="Quantum Physics")

        resp = client.get("/api/search/agents", params={"q": "quantum"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "A2"

    def test_search_filter_by_team(self, client):
        """Search agents filtered by team_id."""
        t1 = client.post("/api/teams/", json={"name": "Team 1"}).json()
        t2 = client.post("/api/teams/", json={"name": "Team 2"}).json()
        self._create_agent(client, t1["id"], name="ML Agent", expertise="ML")
        self._create_agent(client, t2["id"], name="ML Specialist", expertise="ML")

        # Search across all teams
        resp = client.get("/api/search/agents", params={"q": "ML"})
        assert resp.json()["total"] == 2

        # Search within specific team
        resp = client.get("/api/search/agents", params={"q": "ML", "team_id": t1["id"]})
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["team_id"] == t1["id"]

    def test_search_by_title(self, client):
        """Search agents by title."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        self._create_agent(client, team["id"], name="A1", title="Principal Investigator")
        self._create_agent(client, team["id"], name="A2", title="Lab Technician")

        resp = client.get("/api/search/agents", params={"q": "investigator"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
