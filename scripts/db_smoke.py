"""scripts/db_smoke.py — Integration check against PostgreSQL (P2.2).

Using settings.DATABASE_URL:
1. Tests database connectivity. If unreachable, says so plainly.
2. Initializes schema via init_db().
3. Loads data/samples/test.mp3 and generates full fingerprints.
4. Registers track and inserts fingerprints (measures count and elapsed time).
5. Queries find_hits for hashes from a 5s slice (seconds 40-45).
6. Runs find_best_match and prints title, score, offset in seconds, rows inserted, and insert time.
"""

from __future__ import annotations

from pathlib import Path
import sys
import time

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import text

from app.core.config import settings
from app.db.models import Track
from app.db.repository import add_fingerprints, create_track, find_hits
from app.db.session import SessionLocal, engine, init_db
from app.engine.fingerprint import (
    compute_spectrogram,
    find_peaks,
    generate_hashes,
    load_audio,
)
from app.engine.matcher import find_best_match


def main() -> None:
    print(f"Connecting to database at: {settings.DATABASE_URL}")

    # Step 1: Connectivity check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
    except Exception as exc:
        print(
            f"\n[ERROR] Cannot reach PostgreSQL database at {settings.DATABASE_URL}."
        )
        print(f"Details: {exc}")
        print(
            "Please ensure the database container/service is running and accessible."
        )
        sys.exit(1)

    print("PostgreSQL connection established.")

    # Step 2: Initialize schema
    print("Initializing database tables...")
    init_db()

    # Step 3: Fingerprint full sample track
    sample_path = Path("data/samples/test.mp3")
    if not sample_path.exists():
        print(f"[ERROR] Sample audio file not found at {sample_path}")
        sys.exit(1)

    print(f"Loading full audio from {sample_path}...")
    full_audio = load_audio(sample_path)
    sr = settings.SAMPLE_RATE
    duration = len(full_audio) / sr

    print(f"Fingerprinting full track ({duration:.2f}s)...")
    spec = compute_spectrogram(full_audio)
    peaks = find_peaks(spec)
    full_hashes = generate_hashes(peaks)
    print(f"Generated {len(full_hashes)} hashes.")

    # Step 4: Register track and insert fingerprints
    with SessionLocal() as db:
        print("Registering track in database...")
        track = create_track(
            db,
            title="test.mp3",
            owner="Acosign Smoke Test",
            duration_seconds=duration,
        )
        print(f"Track created with ID {track.id}, Content ID: {track.content_id}")

        print(f"Bulk inserting {len(full_hashes)} fingerprints...")
        t0 = time.perf_counter()
        rows_inserted = add_fingerprints(db, track.id, full_hashes)
        insert_time = time.perf_counter() - t0
        print(f"Inserted {rows_inserted} rows in {insert_time:.3f} seconds.")

        # Step 5: Query a 5s slice (seconds 40 to 45)
        print("\nSlicing audio for identification query (seconds 40-45)...")
        start_sample = int(round(40.0 * sr))
        end_sample = int(round(45.0 * sr))
        clip_audio = full_audio[start_sample:end_sample]

        clip_spec = compute_spectrogram(clip_audio)
        clip_peaks = find_peaks(clip_spec)
        clip_hashes = generate_hashes(clip_peaks)
        print(f"Generated {len(clip_hashes)} clip hashes.")

        # Query database for matching hits
        query_hashes = [h for h, _ in clip_hashes]
        print(f"Querying DB for hits across {len(query_hashes)} hashes...")
        db_hits = find_hits(db, query_hashes)
        print(f"Found {len(db_hits)} candidate database hits.")

        # Step 6: Offset matching
        match = find_best_match(clip_hashes, db_hits)
        if match is None:
            print("[FAIL] No match found!")
            sys.exit(1)

        matched_track = db.get(Track, match.track_id)
        track_title = matched_track.title if matched_track else "Unknown"

        seconds_per_frame = settings.HOP_LENGTH / settings.SAMPLE_RATE
        offset_seconds = match.offset_frames * seconds_per_frame

        print("\n" + "=" * 50)
        print("MATCH RESULTS")
        print("=" * 50)
        print(f"Track Title:       {track_title}")
        print(f"Track ID:          {match.track_id}")
        print(f"Score:             {match.score}")
        print(f"Offset Frames:     {match.offset_frames}")
        print(f"Offset Seconds:    {offset_seconds:.2f}s (expected: ~40s)")
        print(f"Confidence:        {match.confidence:.4f}")
        print(f"Rows Inserted:     {rows_inserted}")
        print(f"Insert Time:       {insert_time:.3f}s")
        print("=" * 50)


if __name__ == "__main__":
    main()
