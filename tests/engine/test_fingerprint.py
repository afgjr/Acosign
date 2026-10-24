"""Unit tests for app.engine.fingerprint.

All tests use synthetic audio generated with numpy (AGENT.md Rule 13).
Never depends on external song files or network access.
"""

from __future__ import annotations

import io
from pathlib import Path
import shutil
import subprocess
import tempfile

import librosa
import numpy as np
import pytest
import soundfile as sf

from app.core.config import settings
from app.engine.fingerprint import (
    AudioDecodeError,
    compute_spectrogram,
    find_peaks,
    fingerprint_peaks,
    load_audio,
)


def _generate_sine(
    freq: float = 440.0,
    duration: float = 3.0,
    sr: int = settings.SAMPLE_RATE,
) -> np.ndarray:
    """Generate a pure sine wave as a float32 numpy array."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def _make_wav_bytes(
    audio: np.ndarray,
    sr: int = settings.SAMPLE_RATE,
) -> bytes:
    """Encode numpy audio into WAV bytes."""
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


def _make_mp3_bytes(
    audio: np.ndarray,
    sr: int = settings.SAMPLE_RATE,
) -> bytes:
    """Encode numpy audio into MP3 bytes."""
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="MP3")
    return buf.getvalue()


# ────────────────────────────────────────────────────────────────────────────
# 1. load_audio tests
# ────────────────────────────────────────────────────────────────────────────


def test_load_audio_wav_3s() -> None:
    """3s 440 Hz WAV loads as 1-D float32 with length approximately 3 * SAMPLE_RATE."""
    y_raw = _generate_sine(freq=440.0, duration=3.0)
    wav_bytes = _make_wav_bytes(y_raw)

    y = load_audio(wav_bytes)

    assert isinstance(y, np.ndarray), "Returned object must be a numpy ndarray"
    assert y.ndim == 1, "Returned audio array must be 1-D"
    assert y.dtype == np.float32, "Returned audio array must have float32 dtype"
    expected_len = int(3.0 * settings.SAMPLE_RATE)
    assert abs(len(y) - expected_len) <= 10, (
        f"Length {len(y)} should be close to expected {expected_len}"
    )


def test_load_audio_stereo_and_resampling() -> None:
    """Stereo input becomes mono, and audio at 44100 Hz is resampled to SAMPLE_RATE."""
    sr_input = 44100
    duration = 3.0
    y_left = _generate_sine(freq=440.0, duration=duration, sr=sr_input)
    y_right = _generate_sine(freq=880.0, duration=duration, sr=sr_input)
    stereo = np.column_stack([y_left, y_right])

    stereo_bytes = _make_wav_bytes(stereo, sr=sr_input)
    y = load_audio(stereo_bytes)

    assert y.ndim == 1, "Stereo audio must be converted to 1-D mono"
    assert y.dtype == np.float32, "Audio must be float32"
    expected_len = int(duration * settings.SAMPLE_RATE)
    assert abs(len(y) - expected_len) <= 10, (
        f"Resampled length {len(y)} must be near {expected_len}"
    )


def test_load_audio_mp3_bytes_and_file() -> None:
    """MP3 format is supported both from bytes and from a disk file path."""
    y_raw = _generate_sine(freq=440.0, duration=2.0)
    mp3_bytes = _make_mp3_bytes(y_raw)

    # From bytes
    y_from_bytes = load_audio(mp3_bytes)
    assert y_from_bytes.ndim == 1
    assert y_from_bytes.dtype == np.float32
    assert len(y_from_bytes) > 0

    # From file path
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(mp3_bytes)
        tmp_path = Path(tmp.name)

    try:
        y_from_file = load_audio(tmp_path)
        assert y_from_file.ndim == 1
        assert y_from_file.dtype == np.float32
        assert abs(len(y_from_file) - len(y_from_bytes)) <= 10
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_load_audio_empty_bytes_raises() -> None:
    """Empty bytes input must raise AudioDecodeError."""
    with pytest.raises(AudioDecodeError, match="empty"):
        load_audio(b"")


def test_load_audio_garbage_bytes_raises() -> None:
    """Corrupted / garbage bytes must raise AudioDecodeError."""
    garbage = b"this is completely invalid audio data \x00\xff\xfe\x12\x34"
    with pytest.raises(AudioDecodeError):
        load_audio(garbage)


def test_load_audio_shorter_than_1s_raises() -> None:
    """Audio shorter than 1 second must raise AudioDecodeError."""
    short_audio = _generate_sine(duration=0.5)
    wav_bytes = _make_wav_bytes(short_audio)
    with pytest.raises(AudioDecodeError, match="shorter than"):
        load_audio(wav_bytes)


def test_load_audio_nonexistent_and_empty_file_raises(tmp_path: Path) -> None:
    """Non-existent path or empty file must raise AudioDecodeError."""
    non_existent = tmp_path / "ghost.wav"
    with pytest.raises(AudioDecodeError, match="not found"):
        load_audio(non_existent)

    empty_file = tmp_path / "empty.wav"
    empty_file.touch()
    with pytest.raises(AudioDecodeError, match="empty"):
        load_audio(empty_file)


# ────────────────────────────────────────────────────────────────────────────
# 2. compute_spectrogram tests
# ────────────────────────────────────────────────────────────────────────────


def test_spectrogram_expected_frequency_bin() -> None:
    """A 440 Hz sine wave has its strongest bin within +-1 bin of the expected bin."""
    y = _generate_sine(freq=440.0, duration=3.0)
    spec = compute_spectrogram(y)

    assert spec.ndim == 2, "Spectrogram must be 2-D (freq_bins, frames)"
    expected_freq_bins = settings.N_FFT // 2 + 1
    assert spec.shape[0] == expected_freq_bins, (
        f"Frequency bins count should be {expected_freq_bins}, got {spec.shape[0]}"
    )

    # Bin resolution = SAMPLE_RATE / N_FFT
    freq_per_bin = settings.SAMPLE_RATE / settings.N_FFT
    expected_bin = int(round(440.0 / freq_per_bin))

    # Identify the strongest frequency bin averaged across time frames
    strongest_bin = int(np.argmax(np.mean(spec, axis=1)))
    assert abs(strongest_bin - expected_bin) <= 1, (
        f"Strongest bin {strongest_bin} is not within +-1 of expected {expected_bin}"
    )


def test_spectrogram_empty_array() -> None:
    """Empty audio input returns an empty spectrogram with correct frequency bins."""
    empty_spec = compute_spectrogram(np.array([], dtype=np.float32))
    assert empty_spec.shape[0] == settings.N_FFT // 2 + 1
    assert empty_spec.shape[1] == 0


# ────────────────────────────────────────────────────────────────────────────
# 3. find_peaks & fingerprint_peaks tests
# ────────────────────────────────────────────────────────────────────────────


def test_peaks_two_tone_signal() -> None:
    """A two-tone signal (440 Hz + 1200 Hz) produces peaks near both expected bins."""
    duration = 3.0
    t = np.linspace(0, duration, int(settings.SAMPLE_RATE * duration), endpoint=False)
    y_two = (
        np.sin(2 * np.pi * 440.0 * t) + np.sin(2 * np.pi * 1200.0 * t)
    ).astype(np.float32)

    spec = compute_spectrogram(y_two)
    peaks = find_peaks(spec)

    freq_per_bin = settings.SAMPLE_RATE / settings.N_FFT
    bin_440 = int(round(440.0 / freq_per_bin))
    bin_1200 = int(round(1200.0 / freq_per_bin))

    peak_freqs = {p[0] for p in peaks}
    assert any(abs(b - bin_440) <= 2 for b in peak_freqs), (
        f"Expected peaks near 440 Hz (bin {bin_440}), got {peak_freqs}"
    )
    assert any(abs(b - bin_1200) <= 2 for b in peak_freqs), (
        f"Expected peaks near 1200 Hz (bin {bin_1200}), got {peak_freqs}"
    )


def test_peaks_silence_returns_empty_list() -> None:
    """Pure silence returns an empty list of peaks."""
    y_silence = np.zeros(int(settings.SAMPLE_RATE * 2.0), dtype=np.float32)
    spec = compute_spectrogram(y_silence)
    peaks = find_peaks(spec)
    assert peaks == [], "Silence must produce zero peaks"


def test_peaks_determinism() -> None:
    """Calling find_peaks twice on the same input produces identical output."""
    y = _generate_sine(freq=440.0, duration=3.0)
    spec = compute_spectrogram(y)

    peaks_1 = find_peaks(spec)
    peaks_2 = find_peaks(spec)

    assert peaks_1 == peaks_2, "find_peaks must be strictly deterministic"


def test_peaks_scaled_signal_invariance() -> None:
    """Scaling a rich signal by 0.3 gives nearly the same peak set.

    A pure sine is degenerate: its relative-dB spectrogram is flat outside
    one bin, so tied local maxima can resolve differently at 1x vs 0.3x.
    A multi-tone signal with deterministic noise has unambiguous peaks that
    are loudness-invariant by design of the relative-dB normalisation.

    Two peaks are considered "matched" if the other set contains a peak
    within ±1 freq-bin and ±1 time-frame.  We require a matched fraction
    of >= 0.9 in both directions (symmetric).
    """
    sr = settings.SAMPLE_RATE
    duration = 3.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    # Four tones at well-separated frequencies with different amplitudes
    # so each has an unambiguous local maximum in the spectrogram.
    rng = np.random.default_rng(0)
    y = (
        1.00 * np.sin(2 * np.pi * 300.0 * t)
        + 0.80 * np.sin(2 * np.pi * 700.0 * t)
        + 0.60 * np.sin(2 * np.pi * 1200.0 * t)
        + 0.40 * np.sin(2 * np.pi * 2500.0 * t)
        + 0.02 * rng.standard_normal(len(t))  # small deterministic noise
    ).astype(np.float32)

    y_scaled = (y * 0.3).astype(np.float32)

    peaks_orig   = find_peaks(compute_spectrogram(y))
    peaks_scaled = find_peaks(compute_spectrogram(y_scaled))

    assert len(peaks_orig)   > 0, "Original signal must have peaks"
    assert len(peaks_scaled) > 0, "Scaled signal must have peaks"

    # Proximity-tolerant match: a peak (f, t) is matched if the other set
    # contains at least one peak within ±1 bin in both dimensions.
    def _matched_fraction(
        query: list[tuple[int, int]],
        reference: list[tuple[int, int]],
    ) -> float:
        ref_set = set(reference)
        matched = sum(
            1
            for f, t in query
            if any(
                (f + df, t + dt) in ref_set
                for df in (-1, 0, 1)
                for dt in (-1, 0, 1)
            )
        )
        return matched / len(query) if query else 1.0

    frac_orig_in_scaled = _matched_fraction(peaks_orig, peaks_scaled)
    frac_scaled_in_orig = _matched_fraction(peaks_scaled, peaks_orig)

    assert frac_orig_in_scaled >= 0.9, (
        f"Only {frac_orig_in_scaled:.1%} of original peaks found in scaled set "
        f"(need >= 90%)"
    )
    assert frac_scaled_in_orig >= 0.9, (
        f"Only {frac_scaled_in_orig:.1%} of scaled peaks found in original set "
        f"(need >= 90%)"
    )


def test_peaks_bounds_and_sorting() -> None:
    """All peak indices must be inside spectrogram bounds and sorted by (time_frame, freq_bin)."""
    y = _generate_sine(freq=440.0, duration=3.0)
    spec = compute_spectrogram(y)
    peaks = find_peaks(spec)

    assert len(peaks) > 0, "Non-silent tone must generate peaks"

    num_freq_bins, num_frames = spec.shape
    for f, t in peaks:
        assert 0 <= f < num_freq_bins, f"freq_bin {f} out of bounds [0, {num_freq_bins})"
        assert 0 <= t < num_frames, f"time_frame {t} out of bounds [0, {num_frames})"

    # Verify sort order: (time_frame, freq_bin)
    expected_sorted = sorted(peaks, key=lambda p: (p[1], p[0]))
    assert peaks == expected_sorted, "Peaks must be sorted by (time_frame, freq_bin)"


def test_fingerprint_peaks_convenience() -> None:
    """fingerprint_peaks convenience function produces identical output to the pipeline."""
    y_raw = _generate_sine(freq=440.0, duration=3.0)
    wav_bytes = _make_wav_bytes(y_raw)

    peaks_direct = fingerprint_peaks(wav_bytes)

    y = load_audio(wav_bytes)
    spec = compute_spectrogram(y)
    peaks_pipeline = find_peaks(spec)

    assert peaks_direct == peaks_pipeline, (
        "fingerprint_peaks must match load -> spectrogram -> peaks"
    )


# ────────────────────────────────────────────────────────────────────────────
# 4. ffmpeg fallback tests
# ────────────────────────────────────────────────────────────────────────────


def test_load_audio_ffmpeg_fallback_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch subprocess.run to return WAV bytes and verify fallback path."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/ffmpeg" if cmd == "ffmpeg" else None)

    y_expected = _generate_sine(freq=440.0, duration=3.0)
    fake_wav_bytes = _make_wav_bytes(y_expected)

    called_cmd: list[list[str]] = []

    def mock_run(cmd: list[str], *args, **kwargs) -> subprocess.CompletedProcess:
        called_cmd.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=fake_wav_bytes, stderr=b"")

    monkeypatch.setattr(subprocess, "run", mock_run)

    # Force librosa.load to fail so execution reaches the ffmpeg fallback
    def failing_librosa_load(*args, **kwargs):
        raise RuntimeError("librosa failed to decode container")

    monkeypatch.setattr(librosa, "load", failing_librosa_load)

    dummy_audio = b"CUSTOM_CONTAINER_AUDIO_BYTES_TEST_123456"
    y = load_audio(dummy_audio)

    assert len(called_cmd) == 1, "ffmpeg subprocess must have been called exactly once"
    cmd = called_cmd[0]
    assert "ffmpeg" in cmd[0]
    assert "-vn" in cmd
    assert "-ac" in cmd and "1" in cmd
    assert "-ar" in cmd and str(settings.SAMPLE_RATE) in cmd
    assert "-t" in cmd and str(settings.MAX_DECODE_SECONDS) in cmd
    assert "-f" in cmd and "wav" in cmd
    assert isinstance(y, np.ndarray)
    assert y.ndim == 1
    assert y.dtype == np.float32
    assert abs(len(y) - len(y_expected)) <= 10


def test_load_audio_ffmpeg_garbage_raises_audio_decode_error() -> None:
    """Garbage bytes that fail both librosa and ffmpeg raise AudioDecodeError."""
    garbage = b"NON_AUDIO_GARBAGE_PAYLOAD_XYZ_9876543210"
    with pytest.raises(AudioDecodeError):
        load_audio(garbage)


def test_load_audio_ffmpeg_missing_raises_audio_decode_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When standard decoding fails and ffmpeg is missing on PATH, raise AudioDecodeError."""
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    def failing_librosa_load(*args, **kwargs):
        raise RuntimeError("librosa cannot decode")

    monkeypatch.setattr(librosa, "load", failing_librosa_load)

    dummy_audio = b"CORRUPT_BYTES_NO_FFMPEG"
    with pytest.raises(AudioDecodeError, match="ffmpeg is not installed"):
        load_audio(dummy_audio)


def test_load_audio_real_m4a_with_ffmpeg(tmp_path: Path) -> None:
    """Generate a real M4A with ffmpeg from synthetic WAV and verify load_audio decodes it."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        pytest.skip("ffmpeg not installed on PATH")

    wav_path = tmp_path / "synthetic.wav"
    m4a_path = tmp_path / "synthetic.m4a"

    y_raw = _generate_sine(freq=440.0, duration=3.0)
    wav_bytes = _make_wav_bytes(y_raw)
    wav_path.write_bytes(wav_bytes)

    # Convert to M4A container with AAC audio using ffmpeg
    cmd = [
        ffmpeg_bin,
        "-nostdin",
        "-y",
        "-i",
        str(wav_path),
        "-c:a",
        "aac",
        str(m4a_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert res.returncode == 0, f"ffmpeg failed to create M4A: {res.stderr.decode('utf-8', errors='replace')}"

    # Verify loading from disk path
    y_from_file = load_audio(m4a_path)
    assert isinstance(y_from_file, np.ndarray)
    assert y_from_file.ndim == 1
    assert y_from_file.dtype == np.float32
    expected_samples = int(3.0 * settings.SAMPLE_RATE)
    assert abs(len(y_from_file) - expected_samples) <= int(settings.SAMPLE_RATE * 0.1)

    # Verify loading from raw bytes
    m4a_bytes = m4a_path.read_bytes()
    y_from_bytes = load_audio(m4a_bytes)
    assert isinstance(y_from_bytes, np.ndarray)
    assert y_from_bytes.ndim == 1
    assert y_from_bytes.dtype == np.float32
    assert abs(len(y_from_bytes) - len(y_from_file)) <= 100

