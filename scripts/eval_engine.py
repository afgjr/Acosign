"""scripts/eval_engine.py — Offline robustness evaluation of the fingerprint engine (P1.6).

Evaluates identification accuracy and median match scores across diverse
audio degradations (clean, additive noise at 20dB/10dB/5dB, 0.3x volume scaling,
and 8 kHz low-pass filtering to simulate phone speakers) across multiple clip
lengths (3s, 5s, 10s).

Also tests false-positive rejection by checking queries against DB subsets
excluding the true track.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import sys

# Ensure repository root is in sys.path for standalone script execution
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import librosa
import numpy as np

from app.core.config import settings
from app.engine.fingerprint import (
    compute_spectrogram,
    find_peaks,
    generate_hashes,
    load_audio,
)
from app.engine.matcher import find_best_match

# Supported audio extensions for sample scanning
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}

# Evaluation clip lengths and deterministic track start-time fractions
CLIP_LENGTHS = (3, 5, 10)
START_FRACTIONS = (0.10, 0.30, 0.50, 0.70, 0.85)

VARIANT_NAMES = (
    "clean",
    "noise_20db",
    "noise_10db",
    "noise_5db",
    "volume_0.3x",
    "lowpass_8khz",
)


def discover_audio_files(target_file: Path, samples_dir: Path) -> list[Path]:
    """Gather target file and any other unique audio files found in samples_dir."""
    files_set: set[Path] = set()

    if target_file.exists():
        files_set.add(target_file.resolve())

    if samples_dir.exists() and samples_dir.is_dir():
        for p in samples_dir.iterdir():
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                files_set.add(p.resolve())

    # Return sorted for deterministic track numbering
    return sorted(files_set)


def generate_clip_variants(
    clean_clip: np.ndarray, sr: int, seed: int = 42
) -> dict[str, np.ndarray]:
    """Generate signal variants for evaluation given a clean audio slice."""
    rng = np.random.default_rng(seed)
    p_signal = float(np.mean(clean_clip**2))

    def add_white_noise(snr_db: float) -> np.ndarray:
        if p_signal <= 0.0:
            return clean_clip.copy()
        p_noise = p_signal / (10.0 ** (snr_db / 10.0))
        sigma = np.sqrt(p_noise)
        noise = rng.normal(0.0, sigma, size=len(clean_clip)).astype(np.float32)
        return (clean_clip + noise).astype(np.float32)

    # Phone speaker simulation: resample down to 8000 Hz and back to sr
    clip_8k = librosa.resample(clean_clip, orig_sr=sr, target_sr=8000)
    clip_phone = librosa.resample(clip_8k, orig_sr=8000, target_sr=sr).astype(
        np.float32
    )

    return {
        "clean": clean_clip,
        "noise_20db": add_white_noise(20.0),
        "noise_10db": add_white_noise(10.0),
        "noise_5db": add_white_noise(5.0),
        "volume_0.3x": (clean_clip * 0.3).astype(np.float32),
        "lowpass_8khz": clip_phone,
    }


def format_markdown_table(
    results: dict[str, dict[int, list[tuple[bool, int]]]],
    false_positives: int,
    total_fp_checks: int,
    track_count: int,
) -> str:
    """Format evaluation statistics into a clean Markdown table."""
    lines: list[str] = [
        "## Engine evaluation",
        "",
        f"- **Tracks evaluated:** {track_count}",
        f"- **Start positions per length:** {len(START_FRACTIONS)} ({', '.join(f'{int(f*100)}%' for f in START_FRACTIONS)})",
        f"- **False positives:** {false_positives} / {total_fp_checks} queries (expected: 0)",
        "",
        "| Variant | 3s Clip Acc (Med Score) | 5s Clip Acc (Med Score) | 10s Clip Acc (Med Score) |",
        "|:---|:---:|:---:|:---:|",
    ]

    for variant in VARIANT_NAMES:
        row_cells = [f"**{variant}**"]
        for clip_len in CLIP_LENGTHS:
            entries = results[variant][clip_len]
            if not entries:
                row_cells.append("N/A")
                continue
            acc = 100.0 * sum(1 for correct, _ in entries if correct) / len(entries)
            med_score = statistics.median([score for _, score in entries])
            row_cells.append(f"{acc:.1f}% ({med_score:.0f})")
        lines.append(f"| {' | '.join(row_cells)} |")

    lines.append("")
    return "\n".join(lines)


def run_evaluation(default_audio_path: str = "data/samples/test.mp3") -> str:
    """Run full evaluation and return formatted table string."""
    target_path = Path(default_audio_path)
    samples_dir = Path("data/samples")

    audio_files = discover_audio_files(target_path, samples_dir)
    if not audio_files:
        raise FileNotFoundError(f"No audio files found for evaluation at {target_path}")

    sr = settings.SAMPLE_RATE
    print(f"Loading and fingerprinting {len(audio_files)} track(s)...")

    tracks_data: list[tuple[int, Path, np.ndarray]] = []
    db_hits: list[tuple[int, int, int]] = []

    for idx, path in enumerate(audio_files):
        track_id = idx + 1
        print(f"  Track {track_id}: {path.name}")
        audio = load_audio(path)
        tracks_data.append((track_id, path, audio))

        spec = compute_spectrogram(audio)
        peaks = find_peaks(spec)
        hashes = generate_hashes(peaks)
        for h, t in hashes:
            db_hits.append((h, track_id, t))

    print(f"Total database hashes: {len(db_hits)}")

    # Matrix: variant -> clip_len -> list of (is_correct, score)
    results: dict[str, dict[int, list[tuple[bool, int]]]] = {
        v: {cl: [] for cl in CLIP_LENGTHS} for v in VARIANT_NAMES
    }

    false_positives = 0
    total_fp_checks = 0

    print("\nRunning clip robustness matrix...")
    for track_id, path, audio in tracks_data:
        duration = len(audio) / sr

        # Subset of DB excluding the current track for false-positive validation
        db_other_tracks = [hit for hit in db_hits if hit[1] != track_id]

        for clip_len in CLIP_LENGTHS:
            if duration <= clip_len:
                continue

            for frac_idx, frac in enumerate(START_FRACTIONS):
                start_sec = frac * (duration - clip_len)
                s_idx = int(round(start_sec * sr))
                e_idx = s_idx + int(round(clip_len * sr))
                clean_clip = audio[s_idx:e_idx]
                true_offset_frames = int(round(s_idx / settings.HOP_LENGTH))

                # Deterministic seed per clip combination
                seed = 1000 * track_id + 100 * clip_len + frac_idx
                variants = generate_clip_variants(clean_clip, sr, seed=seed)

                for variant_name, clip_arr in variants.items():
                    clip_spec = compute_spectrogram(clip_arr)
                    clip_peaks = find_peaks(clip_spec)
                    clip_hashes = generate_hashes(clip_peaks)

                    match = find_best_match(clip_hashes, db_hits)

                    is_correct = (
                        match is not None
                        and match.track_id == track_id
                        and abs(match.offset_frames - true_offset_frames) <= 2
                    )
                    score = match.score if match is not None else 0
                    results[variant_name][clip_len].append((is_correct, score))

                    # False positive test: remove track from DB
                    total_fp_checks += 1
                    fp_match = find_best_match(clip_hashes, db_other_tracks)
                    if fp_match is not None:
                        false_positives += 1

    table_md = format_markdown_table(
        results,
        false_positives=false_positives,
        total_fp_checks=total_fp_checks,
        track_count=len(tracks_data),
    )

    # Write results to docs/testing.md
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    testing_doc = docs_dir / "testing.md"

    doc_content = (
        "# Testing Documentation\n\n"
        "This document details the test suites, verification methodologies, and "
        "accuracy evaluations for the Acosign fingerprinting engine.\n\n"
        f"{table_md}\n"
    )
    testing_doc.write_text(doc_content, encoding="utf-8")
    print(f"\nWritten evaluation report to {testing_doc}")

    return table_md


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline robustness evaluation for Acosign engine"
    )
    parser.add_argument(
        "--audio",
        type=str,
        default="data/samples/test.mp3",
        help="Path to default audio file (default: data/samples/test.mp3)",
    )
    args = parser.parse_args()

    table_output = run_evaluation(default_audio_path=args.audio)
    print("\n" + table_output)


if __name__ == "__main__":
    main()
