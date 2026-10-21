"""Unit tests for app.engine.matcher (P1.5).

All tests use synthetic tuples built by hand (AGENT.md Rule 13).
No external files, DB, or network required.
"""

from __future__ import annotations

import random
from app.core.config import settings
from app.engine.matcher import MatchResult, find_best_match, rank_matches


def test_correct_track_wins_over_scattered_hits() -> None:
    """Correct track wins when 30 hashes share offset 100 while another track

    has 30 hits at scattered random offsets.
    """
    planted_offset = 100
    num_hits = 30

    clip_hashes: list[tuple[int, int]] = []
    db_hits: list[tuple[int, int, int]] = []

    # Track 1: 30 hashes aligned at offset 100
    for i in range(num_hits):
        h = 1000 + i
        clip_t = i * 2
        db_t = clip_t + planted_offset
        clip_hashes.append((h, clip_t))
        db_hits.append((h, 1, db_t))

    # Track 2: 30 hits at scattered unique offsets (no offset cluster)
    rng = random.Random(42)
    scattered_offsets = rng.sample(range(500, 2000), num_hits)
    for i, offset in enumerate(scattered_offsets):
        h = 2000 + i
        clip_t = i * 3
        db_t = clip_t + offset
        clip_hashes.append((h, clip_t))
        db_hits.append((h, 2, db_t))

    result = find_best_match(clip_hashes, db_hits)
    assert result is not None
    assert result.track_id == 1
    assert result.score == num_hits
    assert result.offset_frames == planted_offset
    assert result.total_matched == num_hits


def test_scattered_hits_single_track_returns_none() -> None:
    """Scattered hits for a single track (many matched hashes, no common offset)

    must return None because score never reaches min_score.
    """
    num_hits = 30
    clip_hashes: list[tuple[int, int]] = []
    db_hits: list[tuple[int, int, int]] = []

    rng = random.Random(123)
    offsets = rng.sample(range(100, 1000), num_hits)

    for i, offset in enumerate(offsets):
        h = 5000 + i
        clip_t = i
        db_t = clip_t + offset
        clip_hashes.append((h, clip_t))
        db_hits.append((h, 1, db_t))

    # Each hit has a distinct offset, so max offset count is 1 (< min_score default 5)
    result = find_best_match(clip_hashes, db_hits)
    assert result is None


def test_offset_frames_equals_planted_offset() -> None:
    """offset_frames equals the planted offset (db_time - clip_time)."""
    planted_offset = 42
    clip_hashes = [(100 + i, i * 5) for i in range(15)]
    db_hits = [(100 + i, 1, i * 5 + planted_offset) for i in range(15)]

    result = find_best_match(clip_hashes, db_hits)
    assert result is not None
    assert result.offset_frames == planted_offset
    assert result.score == 15


def test_empty_clip_or_empty_db_hits_returns_none() -> None:
    """Empty clip or empty db_hits returns None."""
    sample_clip = [(100, 10)]
    sample_db = [(100, 1, 20)]

    assert find_best_match([], sample_db) is None
    assert find_best_match(sample_clip, []) is None
    assert find_best_match([], []) is None

    assert rank_matches([], sample_db) == []
    assert rank_matches(sample_clip, []) == []
    assert rank_matches([], []) == []


def test_score_below_min_score_returns_none_and_custom_min_score_respected() -> None:
    """Score below min_score returns None; custom min_score is respected."""
    # 8 aligned hits
    clip_hashes = [(100 + i, i) for i in range(8)]
    db_hits = [(100 + i, 1, i + 50) for i in range(8)]

    # Higher threshold -> rejected
    assert find_best_match(clip_hashes, db_hits, min_score=10) is None

    # Exact or lower threshold -> accepted
    res_8 = find_best_match(clip_hashes, db_hits, min_score=8)
    assert res_8 is not None
    assert res_8.score == 8

    res_5 = find_best_match(clip_hashes, db_hits, min_score=5)
    assert res_5 is not None
    assert res_5.score == 8

    # Default settings.MIN_MATCH_SCORE check: 3 hits with default threshold (5) returns None
    few_clip = [(100 + i, i) for i in range(3)]
    few_db = [(100 + i, 1, i + 50) for i in range(3)]
    assert find_best_match(few_clip, few_db) is None


def test_tie_between_tracks_resolves_to_lower_track_id() -> None:
    """Tie between two tracks resolves to the lower track_id (deterministic)."""
    # Track 2 has 20 hits at offset 50
    # Track 1 has 20 hits at offset 50
    clip_hashes = [(100 + i, i) for i in range(20)]
    db_hits = []
    # Add track 2 first to ensure order in db_hits does not break determinism
    for i in range(20):
        db_hits.append((100 + i, 2, i + 50))
    for i in range(20):
        db_hits.append((100 + i, 1, i + 50))

    result = find_best_match(clip_hashes, db_hits)
    assert result is not None
    assert result.track_id == 1
    assert result.score == 20

    # Also check tie between track 7 and track 3
    db_hits_3_7 = []
    for i in range(20):
        db_hits_3_7.append((100 + i, 7, i + 50))
        db_hits_3_7.append((100 + i, 3, i + 50))
    result_3_7 = find_best_match(clip_hashes, db_hits_3_7)
    assert result_3_7 is not None
    assert result_3_7.track_id == 3


def test_hash_occurring_twice_in_clip_handled() -> None:
    """A hash occurring twice in the clip is handled (both offsets counted)."""
    # Hash 999 occurs at clip_time 10 and clip_time 20
    clip_hashes = [
        (999, 10),
        (999, 20),
        (1001, 30),
    ]
    # In DB, track 1 has 999 at db_time 110, and 1001 at db_time 130
    # Offsets:
    # 999 against clip_time 10: offset = 100
    # 999 against clip_time 20: offset = 90
    # 1001 against clip_time 30: offset = 100
    # Offset 100 count: 2 (from 999 and 1001)
    # Offset 90 count: 1 (from 999)
    # Total matched: 3
    db_hits = [
        (999, 1, 110),
        (1001, 1, 130),
    ]

    result = find_best_match(clip_hashes, db_hits, min_score=2)
    assert result is not None
    assert result.track_id == 1
    assert result.score == 2
    assert result.offset_frames == 100
    assert result.total_matched == 3


def test_confidence_in_zero_to_one() -> None:
    """Confidence is in 0..1 and matches score / len(clip_hashes)."""
    # 100 clip hashes, 25 aligned hits for track 1
    clip_hashes = [(i, i) for i in range(100)]
    db_hits = [(i, 1, i + 50) for i in range(25)]

    result = find_best_match(clip_hashes, db_hits)
    assert result is not None
    assert 0.0 <= result.confidence <= 1.0
    assert result.confidence == 0.25

    # 10 clip hashes, all 10 aligned
    full_clip = [(i, i) for i in range(10)]
    full_db = [(i, 1, i + 10) for i in range(10)]
    full_res = find_best_match(full_clip, full_db)
    assert full_res is not None
    assert full_res.confidence == 1.0


def test_rank_matches_returns_at_most_five_sorted_desc() -> None:
    """rank_matches returns at most 5, sorted by score desc."""
    # Create 7 tracks with varying scores: 30, 25, 20, 18, 15, 12, 10
    scores = [30, 25, 20, 18, 15, 12, 10]
    track_ids = [101, 102, 103, 104, 105, 106, 107]

    clip_hashes = [(i, i) for i in range(50)]
    db_hits = []

    for score, track_id in zip(scores, track_ids):
        for i in range(score):
            db_hits.append((i, track_id, i + 50))

    ranked = rank_matches(clip_hashes, db_hits, limit=5)
    assert len(ranked) == 5
    assert [r.track_id for r in ranked] == [101, 102, 103, 104, 105]
    assert [r.score for r in ranked] == [30, 25, 20, 18, 15]

    # Verify descending ordering
    for i in range(len(ranked) - 1):
        assert ranked[i].score >= ranked[i + 1].score
