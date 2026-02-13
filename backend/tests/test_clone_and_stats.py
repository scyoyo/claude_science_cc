import pytest
from app.models import Meeting, MeetingMessage, CodeArtifact


class TestMeetingClone:
    def test_clone_meeting(self, client):
        """Clone a meeting creates a new meeting with same config."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        original = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Experiment 1",
            "description": "Test experiment",
            "max_rounds": 10,
        }).json()

        resp = client.post(f"/api/meetings/{original['id']}/clone")
        assert resp.status_code == 201
        clone = resp.json()
        assert clone["id"] != original["id"]
        assert clone["title"] == "Experiment 1 (copy)"
        assert clone["description"] == "Test experiment"
        assert clone["max_rounds"] == 10
        assert clone["current_round"] == 0
        assert clone["status"] == "pending"

    def test_clone_nonexistent_meeting(self, client):
        """Cloning nonexistent meeting returns 404."""
        resp = client.post("/api/meetings/nonexistent/clone")
        assert resp.status_code == 404


class TestAgentClone:
    def _create_agent(self, client, team_id, name="Agent"):
        return client.post("/api/agents/", json={
            "team_id": team_id,
            "name": name,
            "title": "Scientist",
            "expertise": "ML",
            "goal": "Research",
            "role": "Researcher",
            "model": "gpt-4",
        }).json()

    def test_clone_agent_same_team(self, client):
        """Clone agent within same team."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        original = self._create_agent(client, team["id"], name="Alice")

        resp = client.post(f"/api/agents/{original['id']}/clone")
        assert resp.status_code == 201
        clone = resp.json()
        assert clone["id"] != original["id"]
        assert clone["name"] == "Alice (copy)"
        assert clone["team_id"] == team["id"]
        assert clone["expertise"] == "ML"

    def test_clone_agent_to_different_team(self, client):
        """Clone agent to a different team."""
        t1 = client.post("/api/teams/", json={"name": "Team 1"}).json()
        t2 = client.post("/api/teams/", json={"name": "Team 2"}).json()
        original = self._create_agent(client, t1["id"], name="Bob")

        resp = client.post(f"/api/agents/{original['id']}/clone", params={"team_id": t2["id"]})
        assert resp.status_code == 201
        clone = resp.json()
        assert clone["team_id"] == t2["id"]

    def test_clone_agent_invalid_target_team(self, client):
        """Clone to nonexistent team returns 404."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        original = self._create_agent(client, team["id"])

        resp = client.post(f"/api/agents/{original['id']}/clone", params={"team_id": "fake"})
        assert resp.status_code == 404

    def test_clone_nonexistent_agent(self, client):
        """Cloning nonexistent agent returns 404."""
        resp = client.post("/api/agents/nonexistent/clone")
        assert resp.status_code == 404


class TestTeamStats:
    def test_empty_team_stats(self, client):
        """Stats for a team with no content."""
        team = client.post("/api/teams/", json={"name": "Empty Team"}).json()

        resp = client.get(f"/api/teams/{team['id']}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["team_id"] == team["id"]
        assert data["agent_count"] == 0
        assert data["meeting_count"] == 0
        assert data["completed_meetings"] == 0
        assert data["message_count"] == 0
        assert data["artifact_count"] == 0

    def test_team_stats_with_data(self, client, test_db):
        """Stats reflect actual data counts."""
        team = client.post("/api/teams/", json={"name": "Active Team"}).json()

        # Add agents
        for i in range(3):
            client.post("/api/agents/", json={
                "team_id": team["id"],
                "name": f"Agent {i}",
                "title": "Sci",
                "expertise": "X",
                "goal": "Y",
                "role": "Z",
                "model": "gpt-4",
            })

        # Add meetings
        m1 = Meeting(team_id=team["id"], title="M1", status="completed", current_round=3)
        m2 = Meeting(team_id=team["id"], title="M2", status="pending")
        test_db.add_all([m1, m2])
        test_db.commit()
        test_db.refresh(m1)
        test_db.refresh(m2)

        # Add messages to m1
        for i in range(5):
            test_db.add(MeetingMessage(
                meeting_id=m1.id, role="assistant", agent_name=f"A{i}", content="msg", round_number=1,
            ))

        # Add artifact to m1
        test_db.add(CodeArtifact(meeting_id=m1.id, filename="test.py", content="x=1"))
        test_db.commit()

        resp = client.get(f"/api/teams/{team['id']}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_count"] == 3
        assert data["meeting_count"] == 2
        assert data["completed_meetings"] == 1
        assert data["message_count"] == 5
        assert data["artifact_count"] == 1

    def test_stats_nonexistent_team(self, client):
        """Stats for nonexistent team returns 404."""
        resp = client.get("/api/teams/nonexistent/stats")
        assert resp.status_code == 404
