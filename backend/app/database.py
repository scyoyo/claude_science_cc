from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path
from app.config import settings


def _ensure_table_columns_sqlite(engine, table_name: str, columns_to_add: list[tuple[str, str]]) -> None:
    """Add missing columns to a table for existing SQLite DBs."""
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": table_name},
        )
        if r.fetchone() is None:
            return
        r = conn.execute(text(f"PRAGMA table_info({table_name})"))
        existing = {row[1] for row in r}
    with engine.connect() as conn:
        for name, col_def in columns_to_add:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {col_def}"))
                conn.commit()


def _ensure_meetings_columns_sqlite(engine):
    """Add missing columns to meetings table for existing SQLite DBs (no such column errors)."""
    _ensure_table_columns_sqlite(
        engine,
        "meetings",
        [
            ("agenda", "TEXT DEFAULT ''"),
            ("agenda_questions", "TEXT"),
            ("agenda_rules", "TEXT"),
            ("output_type", "VARCHAR(20) DEFAULT 'code'"),
            ("context_meeting_ids", "TEXT"),
            ("participant_agent_ids", "TEXT"),
            ("meeting_type", "VARCHAR(20) DEFAULT 'team'"),
            ("individual_agent_id", "VARCHAR(36)"),
            ("source_meeting_ids", "TEXT"),
            ("parent_meeting_id", "VARCHAR(36)"),
            ("rewrite_feedback", "TEXT DEFAULT ''"),
            ("agenda_strategy", "VARCHAR(30) DEFAULT 'manual'"),
        ],
    )


def _ensure_teams_columns_sqlite(engine):
    """Add owner_id for V2 auth (nullable); language for team-wide preference."""
    _ensure_table_columns_sqlite(engine, "teams", [
        ("owner_id", "VARCHAR(36)"),
        ("language", "VARCHAR(10) DEFAULT 'en'"),
    ])


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
        _ensure_teams_columns_sqlite(engine)
