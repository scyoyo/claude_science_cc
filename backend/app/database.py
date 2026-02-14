from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path
from app.config import settings


def _ensure_meetings_columns_sqlite(engine):
    """Add missing columns to meetings table for existing SQLite DBs (no such column errors)."""
    with engine.connect() as conn:
        r = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='meetings'"))
        if r.fetchone() is None:
            return
        r = conn.execute(text("PRAGMA table_info(meetings)"))
        existing = {row[1] for row in r}
    columns_to_add = [
        ("agenda", "TEXT DEFAULT ''"),
        ("agenda_questions", "TEXT"),  # stored as JSON list
        ("agenda_rules", "TEXT"),
        ("output_type", "VARCHAR(20) DEFAULT 'code'"),
        ("context_meeting_ids", "TEXT"),
    ]
    with engine.connect() as conn:
        for name, col_def in columns_to_add:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE meetings ADD COLUMN {name} {col_def}"))
                conn.commit()


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
    For SQLite, also add any missing columns to existing tables so old DBs keep working.
    """
    Base.metadata.create_all(bind=engine)
    if settings.DATABASE_URL.startswith("sqlite"):
        _ensure_meetings_columns_sqlite(engine)
