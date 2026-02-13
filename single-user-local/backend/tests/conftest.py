import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.main import app
from app.database import Base, get_db
from app.models import Team, Agent, APIKey, Meeting, MeetingMessage, CodeArtifact, User, UserTeamRole  # Import models to register them with Base
from app.core.cache import InMemoryBackend, set_cache, reset_cache

# Use a file-based SQLite database for testing to avoid threading issues
TEST_DATABASE_URL = "sqlite:///./test.db"


@pytest.fixture(scope="function", autouse=True)
def setup_test_database():
    """Set up and tear down test database for each test"""
    # Create engine and tables
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})

    # Drop all tables first (cleanup from previous tests)
    Base.metadata.drop_all(bind=engine)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    # Override dependency
    app.dependency_overrides[get_db] = override_get_db

    # Fresh cache per test (prevents rate limit carry-over)
    set_cache(InMemoryBackend())

    yield

    # Cleanup
    reset_cache()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

    # Remove test database file
    import os
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture
def client():
    """Create test client"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_db():
    """Create test database session for direct database operations"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
