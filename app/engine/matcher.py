"""app.engine.matcher — offset voting and track matching logic (P1.5).

Implements time-offset voting for landmark hashes:
For each matching hash between query clip and database entries, calculate
the time difference:
    offset = db_time - clip_time
Hashes originating from the same true audio recording share a consistent
offset (the time position where the clip starts in the full track). Hashes
matching by chance produce scattered, random offsets.
Grouping by track_id and finding the peak of the offset histogram yields the
best matching track, its alignment offset, and a confidence score.

Pure module: no database or API dependencies (AGENT.md Rule 8).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class MatchResult:
    """Result of matching an audio clip against fingerprint database hits."""

    track_id: int
    score: int          # hashes agreeing on the best offset
    offset_frames: int  # db_time - clip_time at the best offset
    total_matched: int  # all hash hits for this track (any offset)
    confidence: float   # score / number of clip hashes, 0..1


def find_best_match(
    clip_hashes: list[tuple[int, int]],
    db_hits: list[tuple[int, int, int]],
    min_score: int | None = None,
) -> MatchResult | None:
    """Find the single best matching track using offset histogram voting.

    Args:
        clip_hashes: List of (hash, clip_time) pairs from query audio.
        db_hits: List of (hash, track_id, db_time) hits retrieved from DB.
        min_score: Minimum votes required at the best offset. Defaults to
            settings.MIN_MATCH_SCORE.

    Returns:
        MatchResult if a track meets or exceeds min_score, else None.
    """
    ranked = rank_matches(clip_hashes, db_hits, min_score=min_score, limit=1)
    return ranked[0] if ranked else None


def rank_matches(
    clip_hashes: list[tuple[int, int]],
    db_hits: list[tuple[int, int, int]],
    min_score: int | None = None,
    limit: int = 5,
) -> list[MatchResult]:
    """Rank candidate tracks by offset voting score.

    Args:
        clip_hashes: List of (hash, clip_time) pairs from query audio.
        db_hits: List of (hash, track_id, db_time) hits retrieved from DB.
        min_score: Minimum score required to include a track in results.
            Defaults to settings.MIN_MATCH_SCORE.
        limit: Maximum number of tracks to return (default 5).

    Returns:
        List of MatchResult objects sorted by score descending, ties broken
        by lower track_id (deterministic). At most `limit` results.
    """
    if not clip_hashes or not db_hits:
        return []

    threshold = settings.MIN_MATCH_SCORE if min_score is None else min_score

    # 1. Map hash -> list of clip_times (a hash may appear multiple times in a clip)
    clip_map: dict[int, list[int]] = defaultdict(list)
    for h, clip_time in clip_hashes:
        clip_map[h].append(clip_time)

    # 2. For every DB hit whose hash is in the clip, compute offset = db_time - clip_time
    track_offsets: dict[int, Counter[int]] = defaultdict(Counter)
    track_total: dict[int, int] = defaultdict(int)

    for h, track_id, db_time in db_hits:
        if h in clip_map:
            for clip_time in clip_map[h]:
                offset = db_time - clip_time
                track_offsets[track_id][offset] += 1
                track_total[track_id] += 1

    if not track_offsets:
        return []

    # 3. Per track, score = max count
    num_clip_hashes = len(clip_hashes)
    results: list[MatchResult] = []

    for track_id, offset_counts in track_offsets.items():
        best_score = 0
        best_offset = 0
        for offset, count in offset_counts.items():
            if count > best_score:
                best_score = count
                best_offset = offset
            elif count == best_score:
                # Deterministic tie-breaking for equal offset counts
                if offset < best_offset:
                    best_offset = offset

        if best_score < threshold:
            continue

        confidence = min(1.0, best_score / num_clip_hashes) if num_clip_hashes > 0 else 0.0
        total_matched = track_total[track_id]

        results.append(
            MatchResult(
                track_id=track_id,
                score=best_score,
                offset_frames=best_offset,
                total_matched=total_matched,
                confidence=confidence,
            )
        )

    # 4. Sort by score desc, ties broken by lowest track_id
    results.sort(key=lambda m: (-m.score, m.track_id))

    return results[:limit]
