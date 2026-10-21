"""Pytest fixtures for tests/db using an in-memory SQLite engine (P2.2).

Ensures tests never require an active PostgreSQL instance.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base


@pytest.fixture
def sqlite_engine():
    """In-memory SQLite engine with PRAGMA foreign_keys enabled."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db(sqlite_engine) -> Generator[Session, None, None]:
    """Isolated session per test on the in-memory SQLite engine."""
    testing_session_factory = sessionmaker(
        bind=sqlite_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    session = testing_session_factory()
    try:
        yield session
    finally:
        session.close()
