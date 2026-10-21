"""Unit tests for engine robustness (P1.6).

All tests use synthetic multi-tone harmonic chord sequences (AGENT.md Rule 13).
Completely deterministic, CI-safe, no external files or network required.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.config import settings
from app.engine.fingerprint import compute_spectrogram, find_peaks, generate_hashes
from app.engine.matcher import find_best_match


def _generate_synthetic_track(duration: float = 12.0) -> np.ndarray:
    """Generate a rich, multi-tone harmonic track with distinct chords per second.

    Each second features distinct fundamental frequencies and multiple harmonics
    with subtle frequency modulation to produce sharp, reproducible time-frequency peaks.
    """
    sr = settings.SAMPLE_RATE
    total_samples = int(sr * duration)
    t = np.linspace(0, duration, total_samples, endpoint=False, dtype=np.float32)
    audio = np.zeros_like(t)

    # 12 distinct chords across 12 seconds
    chords = [
        [261, 329, 392, 523, 659],
        [293, 369, 440, 587, 739],
        [329, 415, 493, 659, 830],
        [349, 440, 523, 698, 880],
        [392, 493, 587, 783, 987],
        [440, 554, 659, 880, 1108],
        [493, 622, 739, 987, 1244],
        [523, 659, 783, 1046, 1318],
        [587, 739, 880, 1174, 1479],
        [659, 830, 987, 1318, 1661],
        [698, 880, 1046, 1396, 1760],
        [783, 987, 1174, 1567, 1975],
    ]

    for sec_i, freqs in enumerate(chords):
        s_idx = int(sec_i * sr)
        e_idx = int((sec_i + 1) * sr)
        t_sec = t[s_idx:e_idx]
        sig = np.zeros_like(t_sec)
        for k, f in enumerate(freqs):
            mod = 1.0 + 0.05 * np.sin(2.0 * np.pi * 5.0 * t_sec)
            sig += (1.0 / (k + 1)) * np.sin(2.0 * np.pi * f * mod * t_sec)
        audio[s_idx:e_idx] = sig

    max_val = float(np.max(np.abs(audio)))
    if max_val > 0:
        audio = audio / max_val
    return audio.astype(np.float32)


@pytest.fixture(scope="module")
def synthetic_db() -> tuple[np.ndarray, list[tuple[int, int, int]]]:
    """Precompute synthetic track audio and its database hashes."""
    audio = _generate_synthetic_track(duration=12.0)
    spec = compute_spectrogram(audio)
    peaks = find_peaks(spec)
    hashes = generate_hashes(peaks)
    db_hits = [(h, 1, t) for h, t in hashes]
    return audio, db_hits


def test_clipped_middle_section_matches_planted_track(
    synthetic_db: tuple[np.ndarray, list[tuple[int, int, int]]]
) -> None:
    """A 4-second middle section (seconds 3-7) accurately matches the planted track."""
    audio, db_hits = synthetic_db
    sr = settings.SAMPLE_RATE

    start_sec = 3.0
    end_sec = 7.0
    s_idx = int(round(start_sec * sr))
    e_idx = int(round(end_sec * sr))
    clip = audio[s_idx:e_idx]

    expected_offset = int(round(s_idx / settings.HOP_LENGTH))

    clip_spec = compute_spectrogram(clip)
    clip_peaks = find_peaks(clip_spec)
    clip_hashes = generate_hashes(clip_peaks)

    match = find_best_match(clip_hashes, db_hits)
    assert match is not None, "Clean clipped segment should produce a valid match"
    assert match.track_id == 1
    assert abs(match.offset_frames - expected_offset) <= 2
    assert match.score >= settings.MIN_MATCH_SCORE


def test_noisy_clip_10db_snr_still_matches(
    synthetic_db: tuple[np.ndarray, list[tuple[int, int, int]]]
) -> None:
    """A clip corrupted by additive Gaussian white noise at 10 dB SNR still matches."""
    audio, db_hits = synthetic_db
    sr = settings.SAMPLE_RATE
    rng = np.random.default_rng(42)

    start_sec = 3.0
    end_sec = 7.0
    s_idx = int(round(start_sec * sr))
    e_idx = int(round(end_sec * sr))
    clip = audio[s_idx:e_idx]

    expected_offset = int(round(s_idx / settings.HOP_LENGTH))

    # Add Gaussian white noise at 10 dB SNR
    p_signal = float(np.mean(clip ** 2))
    p_noise = p_signal / (10.0 ** (10.0 / 10.0))
    noise = rng.normal(0.0, np.sqrt(p_noise), size=len(clip)).astype(np.float32)
    noisy_clip = clip + noise

    noisy_spec = compute_spectrogram(noisy_clip)
    noisy_peaks = find_peaks(noisy_spec)
    noisy_hashes = generate_hashes(noisy_peaks)

    match = find_best_match(noisy_hashes, db_hits)
    assert match is not None, "10 dB noisy clip should produce a valid match"
    assert match.track_id == 1
    assert abs(match.offset_frames - expected_offset) <= 2
    assert match.score >= settings.MIN_MATCH_SCORE


def test_unrelated_signal_returns_none(
    synthetic_db: tuple[np.ndarray, list[tuple[int, int, int]]]
) -> None:
    """An unrelated audio signal with distinct non-matching frequencies returns None."""
    _, db_hits = synthetic_db
    sr = settings.SAMPLE_RATE

    t = np.linspace(0, 4.0, int(round(4.0 * sr)), endpoint=False, dtype=np.float32)
    unrel = (
        np.sin(2.0 * np.pi * 143.0 * t) + np.sin(2.0 * np.pi * 211.0 * t)
    ).astype(np.float32)

    unrel_spec = compute_spectrogram(unrel)
    unrel_peaks = find_peaks(unrel_spec)
    unrel_hashes = generate_hashes(unrel_peaks)

    match = find_best_match(unrel_hashes, db_hits)
    assert match is None, "Unrelated audio signal must return None"
