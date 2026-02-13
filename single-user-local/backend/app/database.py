from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path
from app.config import settings


def _create_engine():
    """Create SQLAlchemy engine based on DATABASE_URL."""
    url = settings.DATABASE_URL
    kwargs = {}

    if url.startswith("sqlite"):
        # SQLite-specific: ensure data dir exists, allow multi-thread access
        Path("./data").mkdir(exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}

    return create_engine(url, **kwargs)


engine = _create_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables (dev/single-user mode).

    In production with Alembic, use `alembic upgrade head` instead.
    """
    Base.metadata.create_all(bind=engine)
