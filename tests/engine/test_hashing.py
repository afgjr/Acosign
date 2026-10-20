"""Unit tests for generate_hashes and fingerprint_hashes (P1.4).

All tests use synthetic audio generated with numpy (AGENT.md Rule 13).
Never depends on external song files or network access.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
import soundfile as sf

from app.core.config import settings
from app.engine.fingerprint import (
    _DT_BITS,
    _F_BITS,
    _F_MAX,
    _DT_MAX,
    compute_spectrogram,
    find_peaks,
    fingerprint_hashes,
    generate_hashes,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _sine(freq: float, duration: float, sr: int = settings.SAMPLE_RATE) -> np.ndarray:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def _peaks_from_signal(y: np.ndarray) -> list[tuple[int, int]]:
    return find_peaks(compute_spectrogram(y))


def _wav_bytes(audio: np.ndarray, sr: int = settings.SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


def _unpack(h: int) -> tuple[int, int, int]:
    """Recover (f1, f2, dt) from a packed hash integer."""
    dt = h & _DT_MAX
    f2 = (h >> _DT_BITS) & _F_MAX
    f1 = (h >> (_DT_BITS + _F_BITS)) & _F_MAX
    return f1, f2, dt


def _multitone_signal(
    freqs: list[float],
    note_dur: float = 0.5,
    sr: int = settings.SAMPLE_RATE,
) -> np.ndarray:
    """Concatenate several pure tones to form a sequence."""
    segments = [_sine(f, note_dur, sr) for f in freqs]
    return np.concatenate(segments).astype(np.float32)


# ── test fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def simple_peaks() -> list[tuple[int, int]]:
    """Peaks from a 3-second 440 Hz sine."""
    y = _sine(440.0, 3.0)
    return _peaks_from_signal(y)


@pytest.fixture(scope="module")
def simple_hashes(simple_peaks: list[tuple[int, int]]) -> list[tuple[int, int]]:
    return generate_hashes(simple_peaks)


# ── 1. Determinism ────────────────────────────────────────────────────────────


def test_hashes_determinism(simple_peaks: list[tuple[int, int]]) -> None:
    """Same peaks produce identical hash lists on repeated calls."""
    h1 = generate_hashes(simple_peaks)
    h2 = generate_hashes(simple_peaks)
    assert h1 == h2, "generate_hashes must be strictly deterministic"


# ── 2. FAN_OUT limit ──────────────────────────────────────────────────────────


def test_hashes_max_fan_out_per_anchor(simple_peaks: list[tuple[int, int]]) -> None:
    """No anchor time-frame contributes more than settings.FAN_OUT hashes."""
    hashes = generate_hashes(simple_peaks)
    from collections import Counter

    count_by_anchor: Counter[int] = Counter(t for _, t in hashes)
    for anchor_t, count in count_by_anchor.items():
        assert count <= settings.FAN_OUT, (
            f"Anchor at frame {anchor_t} produced {count} hashes, "
            f"exceeding FAN_OUT={settings.FAN_OUT}"
        )


# ── 3. dt within [MIN_DELTA_T, MAX_DELTA_T] ──────────────────────────────────


def test_hashes_dt_range(simple_hashes: list[tuple[int, int]]) -> None:
    """Every hash, when unpacked, has MIN_DELTA_T <= dt <= MAX_DELTA_T."""
    assert len(simple_hashes) > 0, "Expected non-empty hash list for 440 Hz signal"
    effective_max_dt = min(settings.MAX_DELTA_T, _DT_MAX)
    for h, _ in simple_hashes:
        _, _, dt = _unpack(h)
        assert dt >= settings.MIN_DELTA_T, (
            f"dt={dt} is below MIN_DELTA_T={settings.MIN_DELTA_T}"
        )
        assert dt <= effective_max_dt, (
            f"dt={dt} exceeds effective MAX_DELTA_T={effective_max_dt}"
        )


# ── 4. Roundtrip unpack ───────────────────────────────────────────────────────


def test_hashes_unpack_roundtrip(simple_peaks: list[tuple[int, int]]) -> None:
    """Unpacking every hash recovers the f1, f2, dt used to create it."""
    # Build hashes with small, controlled peaks to verify round-trip precisely
    # Use known, in-range peaks so we can trace each hash.
    controlled_peaks: list[tuple[int, int]] = [
        (100, 0),   # anchor
        (200, 5),   # target: dt=5, f1=100, f2=200
        (300, 10),  # target: dt=10
        (400, 15),  # target: dt=15
        (500, 20),  # target: dt=20
        (600, 25),  # target: dt=25
        (700, 30),  # beyond FAN_OUT=5, should be excluded from anchor(100,0)
    ]
    hashes = generate_hashes(controlled_peaks)
    expected = {
        (5, 200, 100),   # (dt, f2, f1) — but _unpack returns (f1, f2, dt)
    }

    for h, anchor_t in hashes:
        f1, f2, dt = _unpack(h)
        # Reconstruct and verify the hash matches
        expected_hash = (f1 << (_F_BITS + _DT_BITS)) | (f2 << _DT_BITS) | dt
        assert h == expected_hash, (
            f"Unpacked ({f1}, {f2}, {dt}) does not reconstruct hash {h}"
        )
        # Verify dt is consistent with the actual peak times
        # Find the anchor peak with time == anchor_t and freq == f1
        anchor_match = [p for p in controlled_peaks if p[1] == anchor_t and p[0] == f1]
        target_match = [
            p for p in controlled_peaks if p[0] == f2 and (p[1] - anchor_t) == dt
        ]
        assert anchor_match, f"No anchor peak found with f={f1}, t={anchor_t}"
        assert target_match, f"No target peak found with f={f2} at t={anchor_t + dt}"


# ── 5. Time-shift invariance ──────────────────────────────────────────────────


def test_hashes_time_shift_invariance(simple_peaks: list[tuple[int, int]]) -> None:
    """Shifting all peaks by +50 frames: same hash values, anchor times +50."""
    shift = 50
    shifted_peaks = [(f, t + shift) for f, t in simple_peaks]

    hashes_orig = generate_hashes(simple_peaks)
    hashes_shifted = generate_hashes(shifted_peaks)

    assert len(hashes_orig) == len(hashes_shifted), (
        "Time shift must not change the number of hashes"
    )

    hash_vals_orig = [h for h, _ in hashes_orig]
    hash_vals_shifted = [h for h, _ in hashes_shifted]
    assert hash_vals_orig == hash_vals_shifted, (
        "Hash values must be identical after a time shift (dt is relative)"
    )

    anchor_times_orig = [t for _, t in hashes_orig]
    anchor_times_shifted = [t for _, t in hashes_shifted]
    assert all(
        ts - to == shift
        for to, ts in zip(anchor_times_orig, anchor_times_shifted)
    ), "Each anchor time must increase by exactly the shift amount"


# ── 6. Empty and single-peak input ───────────────────────────────────────────


def test_hashes_empty_input() -> None:
    """Empty peak list returns an empty hash list."""
    assert generate_hashes([]) == []


def test_hashes_single_peak() -> None:
    """A single peak has no target to pair with, so returns an empty hash list."""
    assert generate_hashes([(82, 0)]) == []


# ── 7. Clip coverage (full vs 2s middle clip) ─────────────────────────────────


def test_hashes_clip_coverage_in_full_signal() -> None:
    """Middle 2s clip hashes are >= 50% contained in the full-signal hash set.

    6 notes sequenced at 0.5s each (3s total), 440..1400 Hz stepping.
    The middle 2s clip spans note 2 through note 5, which share anchors
    and targets with the full-signal fingerprint.
    """
    freqs = [440.0, 600.0, 800.0, 1000.0, 1200.0, 1400.0]
    note_dur = 0.5
    sr = settings.SAMPLE_RATE

    full_signal = _multitone_signal(freqs, note_dur=note_dur, sr=sr)

    # 2-second middle clip: frames 1s .. 3s
    clip_start = int(1.0 * sr)
    clip_end = int(3.0 * sr)
    clip_signal = full_signal[clip_start:clip_end]

    full_hashes = fingerprint_hashes(_wav_bytes(full_signal))
    clip_hashes = fingerprint_hashes(_wav_bytes(clip_signal))

    assert len(clip_hashes) > 0, "Clip must produce hashes"

    full_hash_vals = {h for h, _ in full_hashes}
    clip_hash_vals = {h for h, _ in clip_hashes}

    overlap_count = len(clip_hash_vals & full_hash_vals)
    coverage = overlap_count / len(clip_hash_vals) if clip_hash_vals else 0.0

    assert coverage >= 0.50, (
        f"Clip hash coverage in full signal is {coverage:.1%}, expected >= 50%"
    )


# ── 8. fingerprint_hashes convenience ────────────────────────────────────────


def test_fingerprint_hashes_matches_pipeline() -> None:
    """fingerprint_hashes produces the same result as the manual pipeline."""
    y = _sine(440.0, 3.0)
    wav = _wav_bytes(y)

    hashes_direct = fingerprint_hashes(wav)

    peaks = find_peaks(compute_spectrogram(y))
    hashes_pipeline = generate_hashes(peaks)

    assert hashes_direct == hashes_pipeline, (
        "fingerprint_hashes must match load -> peaks -> generate_hashes"
    )
