"""Unit tests for app.db repository functions (P2.2).

All tests use the in-memory SQLite fixture from tests/db/conftest.py.
Completely isolated, no PostgreSQL or network required.
"""

from __future__ import annotations

import re
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Fingerprint, Track
from app.db.repository import (
    add_fingerprints,
    create_track,
    delete_track,
    find_hits,
    get_track,
    get_track_by_content_id,
    list_tracks,
)


def test_create_track_generates_unique_content_id_and_stores_fields(
    db: Session,
) -> None:
    """create_track generates a unique 32-char hex content_id and accurately stores fields."""
    t1 = create_track(
        db, title="Symphony No. 5", owner="Beethoven", duration_seconds=185.5
    )
    t2 = create_track(
        db, title="Moonlight Sonata", owner="Beethoven", duration_seconds=310.2
    )

    assert t1.id is not None
    assert t2.id is not None
    assert t1.id != t2.id

    # Verify content_id format: 32-character hexadecimal UUID4
    hex_pattern = re.compile(r"^[0-9a-f]{32}$")
    assert hex_pattern.match(t1.content_id)
    assert hex_pattern.match(t2.content_id)
    assert t1.content_id != t2.content_id

    assert t1.title == "Symphony No. 5"
    assert t1.owner == "Beethoven"
    assert abs(t1.duration_seconds - 185.5) < 1e-5
    assert t1.created_at is not None

    # Retrieve by content_id
    fetched = get_track_by_content_id(db, t1.content_id)
    assert fetched is not None
    assert fetched.id == t1.id


def test_add_fingerprints_returns_count_and_stores_big_hashes(
    db: Session,
) -> None:
    """add_fingerprints returns the right count and stores big hashes (e.g. 2**33 + 7) without overflow."""
    track = create_track(
        db, title="Big Hash Track", owner="Owner A", duration_seconds=60.0
    )

    big_hash = (1 << 33) + 7  # 8,589,934,607 (34-bit value)
    normal_hash = 123456789

    # Generate 5,005 items to verify boundary crossing of 5,000 chunk size
    hashes_to_insert: list[tuple[int, int]] = []
    hashes_to_insert.append((big_hash, 0))
    for i in range(1, 5005):
        hashes_to_insert.append((normal_hash + i, i))

    count = add_fingerprints(db, track.id, hashes_to_insert)
    assert count == 5005

    # Query the big hash back from database
    hits = find_hits(db, [big_hash])
    assert len(hits) == 1
    retrieved_hash, retrieved_track_id, retrieved_offset = hits[0]

    assert retrieved_hash == big_hash, "BigInteger hash must match exactly without overflow"
    assert retrieved_track_id == track.id
    assert retrieved_offset == 0


def test_find_hits_returns_only_requested_hashes_with_correct_data(
    db: Session,
) -> None:
    """find_hits returns only requested hashes with correct track_id/offset."""
    t1 = create_track(db, title="Track 1", owner="Owner 1", duration_seconds=30.0)
    t2 = create_track(db, title="Track 2", owner="Owner 2", duration_seconds=30.0)

    add_fingerprints(
        db,
        t1.id,
        [
            (111, 10),
            (222, 20),
            (333, 30),
        ],
    )
    add_fingerprints(
        db,
        t2.id,
        [
            (222, 50),
            (444, 40),
        ],
    )

    # Query for hash 222 (present in both tracks)
    hits_222 = find_hits(db, [222])
    assert len(hits_222) == 2
    assert (222, t1.id, 10) not in hits_222
    assert (222, t1.id, 20) in hits_222
    assert (222, t2.id, 50) in hits_222

    # Query for hashes 111 and 444
    hits_multi = find_hits(db, [111, 444])
    assert len(hits_multi) == 2
    assert (111, t1.id, 10) in hits_multi
    assert (444, t2.id, 40) in hits_multi

    # Query for nonexistent hash
    hits_none = find_hits(db, [999999])
    assert hits_none == []


def test_find_hits_with_duplicate_and_empty_input(db: Session) -> None:
    """find_hits with duplicate and empty input works properly."""
    track = create_track(db, title="Dup Track", owner="Owner", duration_seconds=10.0)
    add_fingerprints(db, track.id, [(777, 15)])

    # Empty input
    assert find_hits(db, []) == []

    # Duplicate input hashes in query
    duplicate_query = [777, 777, 777, 777]
    hits = find_hits(db, duplicate_query)
    # The hit should only be returned once since input is de-duplicated
    assert len(hits) == 1
    assert hits[0] == (777, track.id, 15)


def test_delete_track_cascades_and_removes_fingerprints(db: Session) -> None:
    """delete_track cascades and removes its associated fingerprints."""
    t1 = create_track(db, title="To Delete", owner="Owner", duration_seconds=20.0)
    t2 = create_track(db, title="To Keep", owner="Owner", duration_seconds=20.0)

    add_fingerprints(db, t1.id, [(888, 5), (889, 6)])
    add_fingerprints(db, t2.id, [(999, 7)])

    # Confirm fingerprints exist
    assert len(find_hits(db, [888, 889])) == 2
    assert len(find_hits(db, [999])) == 1

    # Delete track 1
    deleted = delete_track(db, t1.id)
    assert deleted is True

    # Track 1 no longer exists
    assert get_track(db, t1.id) is None

    # Track 1's fingerprints were cascaded
    assert find_hits(db, [888, 889]) == []

    # Direct query in Fingerprint table confirms zero rows with track_id == t1.id
    remaining = db.execute(
        select(Fingerprint).where(Fingerprint.track_id == t1.id)
    ).scalars().all()
    assert len(remaining) == 0

    # Track 2's fingerprints are untouched
    assert len(find_hits(db, [999])) == 1

    # Deleting non-existent track returns False
    assert delete_track(db, 99999) is False


def test_list_tracks_respects_limit_and_offset(db: Session) -> None:
    """list_tracks respects limit and offset pagination parameters."""
    for i in range(5):
        create_track(
            db, title=f"Track {i}", owner=f"Artist {i}", duration_seconds=100.0 + i
        )

    # First page: limit 2, offset 0
    page_1 = list_tracks(db, limit=2, offset=0)
    assert len(page_1) == 2
    assert page_1[0].title == "Track 0"
    assert page_1[1].title == "Track 1"

    # Second page: limit 2, offset 2
    page_2 = list_tracks(db, limit=2, offset=2)
    assert len(page_2) == 2
    assert page_2[0].title == "Track 2"
    assert page_2[1].title == "Track 3"

    # Third page: limit 2, offset 4
    page_3 = list_tracks(db, limit=2, offset=4)
    assert len(page_3) == 1
    assert page_3[0].title == "Track 4"

    # Empty page beyond count
    page_empty = list_tracks(db, limit=2, offset=10)
    assert page_empty == []
