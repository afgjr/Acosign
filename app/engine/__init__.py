"""app.engine package — audio fingerprinting and matching logic."""

from app.engine.fingerprint import (
    AudioDecodeError,
    compute_spectrogram,
    find_peaks,
    fingerprint_hashes,
    fingerprint_peaks,
    generate_hashes,
    load_audio,
)

__all__ = [
    "AudioDecodeError",
    "load_audio",
    "compute_spectrogram",
    "find_peaks",
    "fingerprint_peaks",
    "generate_hashes",
    "fingerprint_hashes",
]
