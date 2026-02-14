"""Tests for the dashboard stats endpoint."""
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_dashboard_stats_empty():
    """Dashboard returns zeros when database is empty."""
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["total_teams"] == 0
    assert data["total_agents"] == 0
    assert data["total_meetings"] == 0
    assert data["completed_meetings"] == 0
    assert data["total_artifacts"] == 0
    assert data["total_messages"] == 0
    assert data["recent_meetings"] == []
    assert data["teams_overview"] == []


def test_dashboard_stats_with_data():
    """Dashboard counts teams, agents, meetings after creation."""
    # Create a team
    team = client.post("/api/teams/", json={"name": "Dashboard Team", "description": "test"}).json()
    team_id = team["id"]

    # Create agents
    for i in range(3):
        client.post("/api/agents/", json={
            "team_id": team_id, "name": f"Agent {i}", "title": "T",
            "expertise": "E", "goal": "G", "role": "R", "model": "gpt-4",
        })

    # Create a meeting
    client.post("/api/meetings/", json={"team_id": team_id, "title": "M1"})

    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["total_teams"] == 1
    assert data["total_agents"] == 3
    assert data["total_meetings"] == 1
    assert data["completed_meetings"] == 0
    assert len(data["teams_overview"]) == 1
    assert data["teams_overview"][0]["agent_count"] == 3
    assert data["teams_overview"][0]["meeting_count"] == 1


def test_dashboard_recent_meetings_order():
    """Recent meetings are sorted by updated_at descending, limited to 5."""
    team = client.post("/api/teams/", json={"name": "T"}).json()
    tid = team["id"]

    # Create 7 meetings
    for i in range(7):
        client.post("/api/meetings/", json={"team_id": tid, "title": f"Meeting {i}"})

    res = client.get("/api/dashboard/stats")
    data = res.json()
    assert len(data["recent_meetings"]) == 5
    # Each recent meeting should have team_name
    for rm in data["recent_meetings"]:
        assert rm["team_name"] == "T"


def test_dashboard_stats_v1_prefix():
    """Dashboard endpoint accessible via /api/v1/ prefix."""
    res = client.get("/api/v1/dashboard/stats")
    assert res.status_code == 200
    assert "total_teams" in res.json()
