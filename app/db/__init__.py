"""app.db package — SQLAlchemy models, session, and repository functions (Phase 2)."""

from app.db.models import Base, Fingerprint, Track
from app.db.repository import (
    add_fingerprints,
    create_track,
    delete_track,
    find_hits,
    get_track,
    get_track_by_content_id,
    list_tracks,
)
from app.db.session import SessionLocal, engine, get_db, init_db

__all__ = [
    "Base",
    "Track",
    "Fingerprint",
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
    "create_track",
    "add_fingerprints",
    "find_hits",
    "get_track",
    "get_track_by_content_id",
    "list_tracks",
    "delete_track",
]
