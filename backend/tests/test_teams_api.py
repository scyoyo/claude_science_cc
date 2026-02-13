import pytest


def test_create_team(client):
    """Test creating a team"""
    response = client.post("/api/teams/", json={
        "name": "Test Team",
        "description": "A test team",
        "is_public": False
    })

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Team"
    assert "id" in data


def test_list_teams(client):
    """Test listing teams"""
    # Create teams
    client.post("/api/teams/", json={"name": "Team 1"})
    client.post("/api/teams/", json={"name": "Team 2"})

    # List teams
    response = client.get("/api/teams/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["skip"] == 0
    assert data["limit"] == 100


def test_get_team(client):
    """Test getting team details"""
    # Create team
    create_response = client.post("/api/teams/", json={"name": "Test Team"})
    team_id = create_response.json()["id"]

    # Get team
    response = client.get(f"/api/teams/{team_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Team"
    assert "agents" in data


def test_update_team(client):
    """Test updating team"""
    # Create team
    create_response = client.post("/api/teams/", json={"name": "Old Name"})
    team_id = create_response.json()["id"]

    # Update team
    response = client.put(f"/api/teams/{team_id}", json={"name": "New Name"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"


def test_delete_team(client):
    """Test deleting team"""
    # Create team
    create_response = client.post("/api/teams/", json={"name": "Test Team"})
    team_id = create_response.json()["id"]

    # Delete team
    response = client.delete(f"/api/teams/{team_id}")
    assert response.status_code == 204

    # Verify deleted
    response = client.get(f"/api/teams/{team_id}")
    assert response.status_code == 404


def test_get_nonexistent_team(client):
    """Test getting a team that doesn't exist"""
    response = client.get("/api/teams/nonexistent-id")
    assert response.status_code == 404
