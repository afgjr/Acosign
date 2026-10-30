"""Audio fingerprinting engine: loading, spectrogram computation, and peak finding.

Landmark-based peak finding (pure functions, deterministic).
See AGENT.md Rules 1, 2, and 8.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import librosa
import numpy as np
from scipy.ndimage import maximum_filter
import soundfile

from app.core.config import settings


class AudioDecodeError(Exception):
    """Raised when audio data cannot be decoded, is empty, corrupt, or too short."""


def _detect_audio_suffix(data: bytes) -> str:
    """Guess an appropriate file suffix from raw audio file headers."""
    if data.startswith(b"RIFF"):
        return ".wav"
    if data.startswith(b"ID3") or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return ".mp3"
    return ".audio"


def _ffmpeg_decode_file(file_path: str | Path) -> np.ndarray:
    """Decode audio file via ffmpeg subprocess fallback returning float32 mono array."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise AudioDecodeError("ffmpeg is not installed or not found on PATH.")

    cmd = [
        ffmpeg_bin,
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(file_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(settings.SAMPLE_RATE),
        "-t",
        str(settings.MAX_DECODE_SECONDS),
        "-f",
        "wav",
        "-",
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioDecodeError("ffmpeg decoding timed out after 60 seconds.") from exc
    except Exception as exc:
        raise AudioDecodeError(f"ffmpeg subprocess execution failed: {exc}") from exc

    if proc.returncode != 0:
        err_msg = proc.stderr.decode("utf-8", errors="replace").strip()
        raise AudioDecodeError(f"ffmpeg decoding failed (code {proc.returncode}): {err_msg}")

    if not proc.stdout:
        raise AudioDecodeError("ffmpeg produced empty audio output.")

    try:
        y, _ = soundfile.read(io.BytesIO(proc.stdout), dtype="float32")
    except Exception as exc:
        raise AudioDecodeError(f"Failed to read WAV audio produced by ffmpeg: {exc}") from exc

    if y.ndim > 1:
        y = np.mean(y, axis=1)
    return np.asarray(y, dtype=np.float32)


def _load_audio_from_bytes(data: bytes) -> np.ndarray:
    """Decode raw audio bytes in-memory or via a temporary file fallback."""
    if len(data) == 0:
        raise AudioDecodeError("Audio bytes input is empty.")

    # 1. Try in-memory decoding with io.BytesIO first
    try:
        y, _ = librosa.load(io.BytesIO(data), sr=settings.SAMPLE_RATE, mono=True)
        return np.asarray(y, dtype=np.float32)
    except Exception:
        pass

    # 2. If decoding fails, write a temp file and retry (librosa then ffmpeg fallback)
    tmp_path: str | None = None
    try:
        suffix = _detect_audio_suffix(data)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            y, _ = librosa.load(tmp_path, sr=settings.SAMPLE_RATE, mono=True)
            return np.asarray(y, dtype=np.float32)
        except Exception:
            pass

        return _ffmpeg_decode_file(tmp_path)
    finally:
        if tmp_path is not None and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _load_audio_from_path(path: Path) -> np.ndarray:
    """Decode an audio file from a disk path."""
    if not path.is_file():
        raise AudioDecodeError(f"Audio file not found: {path}")
    if path.stat().st_size == 0:
        raise AudioDecodeError(f"Audio file is empty: {path}")

    try:
        y, _ = librosa.load(str(path), sr=settings.SAMPLE_RATE, mono=True)
        return np.asarray(y, dtype=np.float32)
    except Exception:
        pass

    return _ffmpeg_decode_file(path)


def load_audio(source: str | Path | bytes) -> np.ndarray:
    """Load an audio source, returning a mono float32 array at settings.SAMPLE_RATE.

    Accepts a file path (str or Path) or raw audio bytes (WAV, MP3, etc.).
    Rejects empty, corrupt, or audio shorter than settings.MIN_AUDIO_DURATION.

    Args:
        source: File path (str or Path) or raw audio bytes.

    Returns:
        1-D mono float32 numpy array sampled at settings.SAMPLE_RATE.

    Raises:
        AudioDecodeError: If the input is empty, corrupt, cannot be decoded,
            or duration is shorter than settings.MIN_AUDIO_DURATION.
    """
    if isinstance(source, (bytes, bytearray, memoryview)):
        y = _load_audio_from_bytes(bytes(source))
    elif isinstance(source, (str, Path)):
        path_str = str(source).strip()
        if not path_str:
            raise AudioDecodeError("Audio file path cannot be empty.")
        y = _load_audio_from_path(Path(path_str))
    else:
        raise AudioDecodeError(f"Unsupported audio source type: {type(source).__name__}")

    # Ensure 1-D mono float32
    if y.ndim > 1:
        y = np.mean(y, axis=0)
    y = np.asarray(y, dtype=np.float32)

    # Reject audio shorter than minimum duration
    min_samples = int(settings.SAMPLE_RATE * settings.MIN_AUDIO_DURATION)
    if len(y) < min_samples:
        duration = len(y) / settings.SAMPLE_RATE
        raise AudioDecodeError(
            f"Audio duration ({duration:.2f}s, {len(y)} samples) is shorter "
            f"than the minimum required {settings.MIN_AUDIO_DURATION}s."
        )

    return y


def compute_spectrogram(y: np.ndarray) -> np.ndarray:
    """Compute the STFT log-magnitude spectrogram normalized relative to maximum.

    Computes the Short-Time Fourier Transform using settings.N_FFT and
    settings.HOP_LENGTH, converts magnitude to dB scale, and normalizes
    relative to the clip's peak magnitude so loudness does not affect peaks.

    Args:
        y: 1-D audio waveform array (mono float32).

    Returns:
        2-D spectrogram array of shape (freq_bins, frames) in dB above the noise floor.
    """
    if len(y) == 0:
        freq_bins = settings.N_FFT // 2 + 1
        return np.empty((freq_bins, 0), dtype=np.float32)

    stft_matrix = librosa.stft(
        y,
        n_fft=settings.N_FFT,
        hop_length=settings.HOP_LENGTH,
    )
    magnitude = np.abs(stft_matrix)
    max_mag = float(np.max(magnitude))

    if max_mag <= 1e-9:
        # Silence: no significant energy
        return np.zeros_like(magnitude, dtype=np.float32)

    # Convert magnitude to dB relative to maximum, clamped at settings.TOP_DB dynamic range
    spec_db = librosa.amplitude_to_db(magnitude, ref=max_mag, top_db=settings.TOP_DB)

    # Shift so the noise floor (max - TOP_DB) is at 0.0 dB and the maximum peak is at TOP_DB
    spec = spec_db + settings.TOP_DB
    return spec.astype(np.float32)


def find_peaks(spec: np.ndarray) -> list[tuple[int, int]]:
    """Find local maxima in the spectrogram above settings.MIN_AMPLITUDE.

    Uses scipy.ndimage.maximum_filter with settings.PEAK_NEIGHBORHOOD_SIZE
    and filters out peaks whose amplitude does not exceed settings.MIN_AMPLITUDE.
    Results are sorted deterministically by (time_frame, freq_bin).

    Args:
        spec: 2-D spectrogram array of shape (freq_bins, frames).

    Returns:
        List of (freq_bin, time_frame) coordinate tuples sorted by (time_frame, freq_bin).
    """
    if spec.size == 0:
        return []

    # Local maximum filter within the neighborhood box
    filtered = maximum_filter(spec, size=settings.PEAK_NEIGHBORHOOD_SIZE)
    mask = (spec == filtered) & (spec > settings.MIN_AMPLITUDE)

    freq_indices, time_indices = np.where(mask)
    peaks = [(int(f), int(t)) for f, t in zip(freq_indices, time_indices)]
    # Deterministic sort order: primary key time_frame, secondary key freq_bin
    peaks.sort(key=lambda p: (p[1], p[0]))
    return peaks


def fingerprint_peaks(source: str | Path | bytes) -> list[tuple[int, int]]:
    """Convenience pipeline: load audio -> compute spectrogram -> find peaks.

    Args:
        source: Audio file path (str or Path) or raw audio bytes.

    Returns:
        List of (freq_bin, time_frame) peak coordinates sorted by (time_frame, freq_bin).
    """
    y = load_audio(source)
    spec = compute_spectrogram(y)
    return find_peaks(spec)


# ── Hash generation ────────────────────────────────────────────────────────
#
# Bit-packing layout: hash = (f1 << 22) | (f2 << 10) | dt
#
#   Field  Bits  Max value  Notes
#   ─────  ────  ─────────  ──────────────────────────────────────────────
#   f1     12    4095       freq-bin of the anchor peak  (N_FFT//2 = 2048)
#   f2     12    4095       freq-bin of the target peak  (same range)
#   dt     10    1023       time-frame gap (frames, not seconds)
#
# Total: 34 bits → fits comfortably in a Python int / SQLite INTEGER.
#
# Pairs whose f1, f2, or dt would overflow these limits are skipped so the
# invariant "unpacking always recovers the original values" holds exactly.
#
_F_BITS = 12       # bits reserved for each frequency-bin field
_DT_BITS = 10      # bits reserved for the delta-time field
_F_MAX = (1 << _F_BITS) - 1    # 4095 — maximum valid freq bin
_DT_MAX = (1 << _DT_BITS) - 1  # 1023 — maximum valid dt in frames


def generate_hashes(
    peaks: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Generate fingerprint hashes from a sorted list of (freq_bin, time_frame) peaks.

    For each anchor peak, pairs it with up to settings.FAN_OUT following peaks
    whose time-frame gap dt satisfies:
        settings.MIN_DELTA_T <= dt <= settings.MAX_DELTA_T

    Candidate targets are selected nearest-in-time first; ties in dt are broken
    by freq_bin (ascending) to guarantee determinism.

    Hash encoding (bit-packed integer, 34 bits total):
        hash = (f1 << 22) | (f2 << 10) | dt
        where f1, f2 are clamped to 12 bits and dt to 10 bits.
    Pairs whose values exceed the bit-field limits are silently skipped.

    Args:
        peaks: List of (freq_bin, time_frame) tuples sorted by (time_frame, freq_bin).

    Returns:
        List of (hash_value, anchor_time_frame) tuples sorted by
        (anchor_time_frame, hash_value).
    """
    min_dt: int = settings.MIN_DELTA_T
    max_dt: int = min(settings.MAX_DELTA_T, _DT_MAX)  # clamp to bit-field limit
    fan_out: int = settings.FAN_OUT

    results: list[tuple[int, int]] = []

    n = len(peaks)
    for anchor_idx in range(n):
        f1, t1 = peaks[anchor_idx]
        if f1 > _F_MAX:
            # anchor freq bin overflows 12 bits — skip
            continue

        # Collect candidates: peaks after anchor within [MIN_DELTA_T, max_dt]
        # They are already sorted by (time_frame, freq_bin), so we scan forward.
        candidates: list[tuple[int, int, int]] = []  # (dt, f2, target_idx)
        for target_idx in range(anchor_idx + 1, n):
            f2, t2 = peaks[target_idx]
            dt = t2 - t1
            if dt < min_dt:
                continue  # same or too-close frame (shouldn't happen with sorted input)
            if dt > max_dt:
                break  # peaks are time-sorted; no further target can qualify
            if f2 > _F_MAX:
                continue  # target freq bin overflows 12 bits
            candidates.append((dt, f2, target_idx))

        # Sort candidates: nearest-in-time first, break ties by freq_bin
        candidates.sort(key=lambda c: (c[0], c[1]))

        # Take up to FAN_OUT
        for dt, f2, _ in candidates[:fan_out]:
            hash_val = (f1 << (_F_BITS + _DT_BITS)) | (f2 << _DT_BITS) | dt
            results.append((hash_val, t1))

    # Deterministic output order: primary key anchor_time_frame, secondary hash_value
    results.sort(key=lambda r: (r[1], r[0]))
    return results


def fingerprint_hashes(source: str | Path | bytes) -> list[tuple[int, int]]:
    """Convenience pipeline: load audio -> peaks -> hashes.

    Args:
        source: Audio file path (str or Path) or raw audio bytes.

    Returns:
        List of (hash_value, anchor_time_frame) tuples sorted by
        (anchor_time_frame, hash_value).
    """
    peaks = fingerprint_peaks(source)
    return generate_hashes(peaks)

