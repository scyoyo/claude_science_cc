"""Tests for V9 features: meeting comparison, agent metrics, team import/export."""

import pytest
from app.models import Meeting, MeetingMessage, Agent


class TestMeetingComparison:
    def _setup_meetings(self, client, test_db):
        team = client.post("/api/teams/", json={"name": "Team"}).json()

        m1 = Meeting(team_id=team["id"], title="Experiment A", current_round=3, status="completed")
        m2 = Meeting(team_id=team["id"], title="Experiment B", current_round=2, status="completed")
        test_db.add_all([m1, m2])
        test_db.commit()
        test_db.refresh(m1)
        test_db.refresh(m2)

        # Messages for m1 (Alice + Bob)
        test_db.add(MeetingMessage(meeting_id=m1.id, role="assistant", agent_name="Alice", content="msg", round_number=1))
        test_db.add(MeetingMessage(meeting_id=m1.id, role="assistant", agent_name="Bob", content="msg", round_number=1))
        # Messages for m2 (Alice + Charlie)
        test_db.add(MeetingMessage(meeting_id=m2.id, role="assistant", agent_name="Alice", content="msg", round_number=1))
        test_db.add(MeetingMessage(meeting_id=m2.id, role="assistant", agent_name="Charlie", content="msg", round_number=1))
        test_db.commit()

        return m1, m2

    def test_compare_meetings(self, client, test_db):
        """Compare two meetings returns structured comparison."""
        m1, m2 = self._setup_meetings(client, test_db)
        resp = client.get("/api/meetings/compare", params={"ids": f"{m1.id},{m2.id}"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["meetings"]) == 2
        assert data["meetings"][0]["title"] == "Experiment A"
        assert data["meetings"][1]["title"] == "Experiment B"
        assert "Alice" in data["shared_participants"]
        assert "Bob" in data["unique_to_first"]
        assert "Charlie" in data["unique_to_second"]

    def test_compare_requires_two_ids(self, client):
        """Compare requires exactly 2 IDs."""
        resp = client.get("/api/meetings/compare", params={"ids": "single-id"})
        assert resp.status_code == 400

    def test_compare_nonexistent(self, client, test_db):
        """Compare with nonexistent meeting returns 404."""
        team = client.post("/api/teams/", json={"name": "T"}).json()
        m = client.post("/api/meetings/", json={"team_id": team["id"], "title": "M"}).json()
        resp = client.get("/api/meetings/compare", params={"ids": f"{m['id']},nonexistent"})
        assert resp.status_code == 404


class TestAgentMetrics:
    def test_agent_metrics(self, client, test_db):
        """Agent metrics show participation stats."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        agent = client.post("/api/agents/", json={
            "team_id": team["id"], "name": "Alice", "title": "Sci",
            "expertise": "ML", "goal": "Research", "role": "R", "model": "gpt-4",
        }).json()

        meeting = Meeting(team_id=team["id"], title="M", status="completed", current_round=2)
        test_db.add(meeting)
        test_db.commit()
        test_db.refresh(meeting)

        # Add messages from this agent
        for i in range(5):
            test_db.add(MeetingMessage(
                meeting_id=meeting.id, agent_id=agent["id"],
                role="assistant", agent_name="Alice",
                content="x" * 100, round_number=(i % 2) + 1,
            ))
        test_db.commit()

        resp = client.get(f"/api/agents/{agent['id']}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_name"] == "Alice"
        assert data["total_meetings"] == 1
        assert data["total_messages"] == 5
        assert data["avg_message_length"] == 100

    def test_metrics_no_messages(self, client):
        """Metrics for agent with no messages."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        agent = client.post("/api/agents/", json={
            "team_id": team["id"], "name": "Bob", "title": "Sci",
            "expertise": "X", "goal": "Y", "role": "Z", "model": "gpt-4",
        }).json()

        resp = client.get(f"/api/agents/{agent['id']}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_meetings"] == 0
        assert data["total_messages"] == 0
        assert data["most_active_round"] is None

    def test_metrics_nonexistent(self, client):
        """Metrics for nonexistent agent returns 404."""
        resp = client.get("/api/agents/nonexistent/metrics")
        assert resp.status_code == 404


class TestTeamImportExport:
    def test_export_team(self, client):
        """Export team as JSON config."""
        team = client.post("/api/teams/", json={"name": "Export Team", "description": "Test"}).json()
        client.post("/api/agents/", json={
            "team_id": team["id"], "name": "Agent1", "title": "Sci",
            "expertise": "ML", "goal": "Research", "role": "R", "model": "gpt-4",
        })
        client.post("/api/agents/", json={
            "team_id": team["id"], "name": "Agent2", "title": "Eng",
            "expertise": "SW", "goal": "Build", "role": "Dev", "model": "claude-3",
        })

        resp = client.get(f"/api/teams/{team['id']}/export")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Export Team"
        assert len(data["agents"]) == 2
        assert data["agents"][0]["name"] in ("Agent1", "Agent2")

    def test_import_team(self, client):
        """Import team from JSON config."""
        config = {
            "name": "Imported Team",
            "description": "From config",
            "agents": [
                {"name": "A1", "title": "Sci", "expertise": "ML", "goal": "R", "role": "R", "model": "gpt-4"},
                {"name": "A2", "title": "Eng", "expertise": "SW", "goal": "B", "role": "D", "model": "gpt-4"},
            ],
        }
        resp = client.post("/api/teams/import", json=config)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Imported Team"
        assert len(data["agents"]) == 2

    def test_roundtrip_export_import(self, client):
        """Export then import produces equivalent team."""
        team = client.post("/api/teams/", json={"name": "Roundtrip Team"}).json()
        client.post("/api/agents/", json={
            "team_id": team["id"], "name": "Agent", "title": "Sci",
            "expertise": "Bio", "goal": "Discover", "role": "Lead", "model": "gpt-4",
        })

        exported = client.get(f"/api/teams/{team['id']}/export").json()
        imported = client.post("/api/teams/import", json=exported).json()

        assert imported["name"] == exported["name"]
        assert len(imported["agents"]) == len(exported["agents"])
        assert imported["agents"][0]["name"] == exported["agents"][0]["name"]

    def test_import_missing_name(self, client):
        """Import without name field fails."""
        resp = client.post("/api/teams/import", json={"agents": []})
        assert resp.status_code == 400

    def test_export_nonexistent(self, client):
        """Export nonexistent team returns 404."""
        resp = client.get("/api/teams/nonexistent/export")
        assert resp.status_code == 404
