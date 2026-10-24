"""Database session management and connection setup (P2.1)."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base

# SQLAlchemy 2.0 engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency generator yielding a database session for FastAPI endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None) -> None:
    """Create all database tables defined in metadata and ensure metadata columns exist."""
    target = target_engine or engine
    Base.metadata.create_all(bind=target)

    columns = [
        ("album", "VARCHAR(200)"),
        ("genre", "VARCHAR(200)"),
        ("release_year", "INTEGER"),
        ("isrc", "VARCHAR(200)"),
        ("license_type", "VARCHAR(200)"),
        ("description", "TEXT"),
    ]
    with target.connect() as conn:
        if conn.dialect.name == "postgresql":
            for col_name, col_type in columns:
                try:
                    conn.execute(text(f"ALTER TABLE tracks ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    conn.commit()
                except Exception:
                    pass
        else:
            try:
                insp = inspect(conn)
                if "tracks" in insp.get_table_names():
                    existing = {c["name"] for c in insp.get_columns("tracks")}
                    for col_name, col_type in columns:
                        if col_name not in existing:
                            conn.execute(text(f"ALTER TABLE tracks ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
            except Exception:
                pass
