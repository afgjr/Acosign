"""Database repository operations for tracks and fingerprints (P2.2).

Provides pure database queries and bulk inserts with chunking and de-duplication.
"""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.db.models import Fingerprint, Track

# Chunk sizes per specifications (P2.2)
INSERT_CHUNK_SIZE = 5000
QUERY_CHUNK_SIZE = 500


def create_track(
    db: Session,
    title: str,
    owner: str,
    duration_seconds: float,
    album: str | None = None,
    genre: str | None = None,
    release_year: int | None = None,
    isrc: str | None = None,
    license_type: str | None = None,
    description: str | None = None,
) -> Track:
    """Create a new track with a unique content_id (UUID4 hex)."""
    track = Track(
        content_id=uuid.uuid4().hex,
        title=title,
        owner=owner,
        duration_seconds=duration_seconds,
        album=album,
        genre=genre,
        release_year=release_year,
        isrc=isrc,
        license_type=license_type,
        description=description,
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def add_fingerprints(
    db: Session,
    track_id: int,
    hashes: list[tuple[int, int]],
) -> int:
    """Bulk insert fingerprints for a track in chunks of 5000.

    Args:
        db: Database session.
        track_id: ID of the parent track.
        hashes: List of (hash, offset) tuples.

    Returns:
        Total number of fingerprints inserted.
    """
    if not hashes:
        return 0

    total_inserted = 0
    for i in range(0, len(hashes), INSERT_CHUNK_SIZE):
        chunk = hashes[i : i + INSERT_CHUNK_SIZE]
        records = [
            {"hash": h, "track_id": track_id, "offset": offset}
            for h, offset in chunk
        ]
        db.execute(insert(Fingerprint), records)
        total_inserted += len(records)

    db.commit()
    return total_inserted


def find_hits(
    db: Session,
    hashes: list[int],
) -> list[tuple[int, int, int]]:
    """Query database for candidate matches against a list of hashes.

    De-duplicates the input hashes first and queries in chunks of 500 hashes.

    Args:
        db: Database session.
        hashes: List of integer hashes from the query clip.

    Returns:
        List of (hash, track_id, offset) tuples.
    """
    if not hashes:
        return []

    # De-duplicate input hashes preserving order
    unique_hashes = list(dict.fromkeys(hashes))

    hits: list[tuple[int, int, int]] = []
    for i in range(0, len(unique_hashes), QUERY_CHUNK_SIZE):
        chunk = unique_hashes[i : i + QUERY_CHUNK_SIZE]
        stmt = select(
            Fingerprint.hash,
            Fingerprint.track_id,
            Fingerprint.offset,
        ).where(Fingerprint.hash.in_(chunk))
        rows = db.execute(stmt).all()
        for row in rows:
            hits.append((row[0], row[1], row[2]))

    return hits


def get_track(db: Session, track_id: int) -> Track | None:
    """Fetch track by primary key ID."""
    return db.get(Track, track_id)


def get_track_by_content_id(db: Session, content_id: str) -> Track | None:
    """Fetch track by unique UUID4 hex content_id."""
    stmt = select(Track).where(Track.content_id == content_id)
    return db.execute(stmt).scalar_one_or_none()


def list_tracks(
    db: Session,
    limit: int = 100,
    offset: int = 0,
) -> list[Track]:
    """List tracks ordered by primary key with limit and offset pagination."""
    stmt = select(Track).order_by(Track.id).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


def delete_track(db: Session, track_id: int) -> bool:
    """Delete a track and cascade deletion of its fingerprints.

    Returns True if track existed and was deleted, False otherwise.
    """
    track = db.get(Track, track_id)
    if track is None:
        return False
    db.delete(track)
    db.commit()
    return True
