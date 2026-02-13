import pytest


@pytest.fixture
def sample_team(client):
    """Create a sample team"""
    response = client.post("/api/teams/", json={"name": "Test Team"})
    return response.json()


def test_create_agent(client, sample_team):
    """Test creating an agent"""
    response = client.post("/api/agents/", json={
        "team_id": sample_team["id"],
        "name": "Dr. Smith",
        "title": "Research Lead",
        "expertise": "Machine Learning",
        "goal": "Develop ML models",
        "role": "Lead research",
        "model": "gpt-4",
        "model_params": {"temperature": 0.7}
    })

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Dr. Smith"
    assert data["model"] == "gpt-4"
    assert "system_prompt" in data
    assert "Research Lead" in data["system_prompt"]


def test_create_agent_invalid_team(client):
    """Test creating an agent with non-existent team"""
    response = client.post("/api/agents/", json={
        "team_id": "nonexistent-id",
        "name": "Dr. Smith",
        "title": "Research Lead",
        "expertise": "Machine Learning",
        "goal": "Develop ML models",
        "role": "Lead research",
        "model": "gpt-4"
    })

    assert response.status_code == 404


def test_list_team_agents(client, sample_team):
    """Test listing agents in a team"""
    # Create agents
    client.post("/api/agents/", json={
        "team_id": sample_team["id"],
        "name": "Agent 1",
        "title": "Title",
        "expertise": "Expertise",
        "goal": "Goal",
        "role": "Role",
        "model": "gpt-4"
    })
    client.post("/api/agents/", json={
        "team_id": sample_team["id"],
        "name": "Agent 2",
        "title": "Title",
        "expertise": "Expertise",
        "goal": "Goal",
        "role": "Role",
        "model": "gpt-4"
    })

    # List agents
    response = client.get(f"/api/agents/team/{sample_team['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_get_agent(client, sample_team):
    """Test getting agent details"""
    # Create agent
    create_response = client.post("/api/agents/", json={
        "team_id": sample_team["id"],
        "name": "Dr. Smith",
        "title": "Title",
        "expertise": "Expertise",
        "goal": "Goal",
        "role": "Role",
        "model": "gpt-4"
    })
    agent_id = create_response.json()["id"]

    # Get agent
    response = client.get(f"/api/agents/{agent_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Dr. Smith"


def test_update_agent(client, sample_team):
    """Test updating agent"""
    # Create agent
    create_response = client.post("/api/agents/", json={
        "team_id": sample_team["id"],
        "name": "Old Name",
        "title": "Title",
        "expertise": "Expertise",
        "goal": "Goal",
        "role": "Role",
        "model": "gpt-4"
    })
    agent_id = create_response.json()["id"]

    # Update agent
    response = client.put(f"/api/agents/{agent_id}", json={
        "name": "New Name",
        "model": "claude-3-opus"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["model"] == "claude-3-opus"


def test_delete_agent(client, sample_team):
    """Test deleting agent"""
    # Create agent
    create_response = client.post("/api/agents/", json={
        "team_id": sample_team["id"],
        "name": "Agent",
        "title": "Title",
        "expertise": "Expertise",
        "goal": "Goal",
        "role": "Role",
        "model": "gpt-4"
    })
    agent_id = create_response.json()["id"]

    # Delete agent
    response = client.delete(f"/api/agents/{agent_id}")
    assert response.status_code == 204

    # Verify deleted
    response = client.get(f"/api/agents/{agent_id}")
    assert response.status_code == 404


def test_cascade_delete_agents_with_team(client, sample_team):
    """Test that deleting a team cascades to delete agents"""
    # Create agent
    client.post("/api/agents/", json={
        "team_id": sample_team["id"],
        "name": "Agent",
        "title": "Title",
        "expertise": "Expertise",
        "goal": "Goal",
        "role": "Role",
        "model": "gpt-4"
    })

    # Delete team
    response = client.delete(f"/api/teams/{sample_team['id']}")
    assert response.status_code == 204

    # Verify agents are gone
    response = client.get(f"/api/agents/team/{sample_team['id']}")
    assert response.status_code == 200
    assert response.json()["total"] == 0
