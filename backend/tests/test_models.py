import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Team, Agent


@pytest.fixture(scope="function")
def db_session():
    """Create test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()

    yield db

    db.close()


def test_create_team(db_session):
    """Test creating a team"""
    team = Team(
        name="Test Team",
        description="A test team"
    )
    db_session.add(team)
    db_session.commit()

    assert team.id is not None
    assert team.name == "Test Team"


def test_create_agent(db_session):
    """Test creating an agent"""
    team = Team(name="Test Team")
    db_session.add(team)
    db_session.commit()

    agent = Agent(
        team_id=team.id,
        name="Dr. Smith",
        title="Research Lead",
        expertise="Machine Learning",
        goal="Develop ML models",
        role="Lead research and development",
        system_prompt="You are a Research Lead...",
        model="gpt-4",
        model_params={"temperature": 0.7}
    )
    db_session.add(agent)
    db_session.commit()

    assert agent.id is not None
    assert agent.name == "Dr. Smith"
    assert agent.team.name == "Test Team"


def test_cascade_delete(db_session):
    """Test cascade deletion"""
    team = Team(name="Test Team")
    db_session.add(team)
    db_session.commit()

    agent = Agent(
        team_id=team.id,
        name="Agent 1",
        title="Title",
        expertise="Expertise",
        goal="Goal",
        role="Role",
        system_prompt="Prompt",
        model="gpt-4"
    )

    db_session.add(agent)
    db_session.commit()

    agent_id = agent.id

    # Delete team
    db_session.delete(team)
    db_session.commit()

    # Agent should be deleted too
    assert db_session.query(Agent).filter(Agent.id == agent_id).first() is None


def test_mirror_agent(db_session):
    """Test creating mirror agent"""
    team = Team(name="Test Team")
    db_session.add(team)
    db_session.commit()

    primary_agent = Agent(
        team_id=team.id,
        name="Primary Agent",
        title="Researcher",
        expertise="AI",
        goal="Research",
        role="Lead",
        system_prompt="You are a researcher...",
        model="gpt-4"
    )
    db_session.add(primary_agent)
    db_session.commit()

    mirror_agent = Agent(
        team_id=team.id,
        name="Mirror Agent",
        title="Researcher",
        expertise="AI",
        goal="Research",
        role="Lead",
        system_prompt="You are a researcher...",
        model="deepseek",
        is_mirror=True,
        primary_agent_id=primary_agent.id
    )
    db_session.add(mirror_agent)
    db_session.commit()

    assert mirror_agent.is_mirror is True
    assert mirror_agent.primary_agent_id == primary_agent.id
