import pytest


def _agent_data(team_id, name="Agent", **kwargs):
    defaults = {
        "team_id": team_id,
        "name": name,
        "title": "Scientist",
        "expertise": "General",
        "goal": "Research",
        "role": "Researcher",
        "model": "gpt-4",
    }
    defaults.update(kwargs)
    return defaults


class TestBatchCreate:
    def test_batch_create_agents(self, client):
        """Create multiple agents in one request."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        agents = [
            _agent_data(team["id"], name="Agent 1"),
            _agent_data(team["id"], name="Agent 2"),
            _agent_data(team["id"], name="Agent 3"),
        ]
        resp = client.post("/api/agents/batch", json=agents)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 3
        names = {a["name"] for a in data}
        assert names == {"Agent 1", "Agent 2", "Agent 3"}
        # Verify system prompts generated
        for agent in data:
            assert agent["system_prompt"]

    def test_batch_create_invalid_team(self, client):
        """Batch create fails if any team ID is invalid."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        agents = [
            _agent_data(team["id"], name="Good"),
            _agent_data("nonexistent-team", name="Bad"),
        ]
        resp = client.post("/api/agents/batch", json=agents)
        assert resp.status_code == 404
        assert "nonexistent-team" in resp.json()["detail"]

    def test_batch_create_empty_list(self, client):
        """Batch create rejects empty list."""
        resp = client.post("/api/agents/batch", json=[])
        assert resp.status_code == 400

    def test_batch_create_too_many(self, client):
        """Batch create rejects more than 50 agents."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        agents = [_agent_data(team["id"], name=f"A{i}") for i in range(51)]
        resp = client.post("/api/agents/batch", json=agents)
        assert resp.status_code == 400
        assert "50" in resp.json()["detail"]


class TestBatchDelete:
    def test_batch_delete_agents(self, client):
        """Delete multiple agents by IDs."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        a1 = client.post("/api/agents/", json=_agent_data(team["id"], name="A1")).json()
        a2 = client.post("/api/agents/", json=_agent_data(team["id"], name="A2")).json()
        a3 = client.post("/api/agents/", json=_agent_data(team["id"], name="A3")).json()

        resp = client.request("DELETE", "/api/agents/batch", json=[a1["id"], a2["id"]])
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 2

        # Verify a3 still exists
        resp = client.get(f"/api/agents/{a3['id']}")
        assert resp.status_code == 200

        # Verify a1, a2 gone
        assert client.get(f"/api/agents/{a1['id']}").status_code == 404
        assert client.get(f"/api/agents/{a2['id']}").status_code == 404

    def test_batch_delete_nonexistent(self, client):
        """Batch delete with nonexistent IDs returns 0 deleted."""
        resp = client.request("DELETE", "/api/agents/batch", json=["fake-id-1", "fake-id-2"])
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 0

    def test_batch_delete_empty_list(self, client):
        """Batch delete rejects empty list."""
        resp = client.request("DELETE", "/api/agents/batch", json=[])
        assert resp.status_code == 400
