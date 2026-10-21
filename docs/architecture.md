# Acosign Architecture — Fingerprint Engine

This document details the architectural design and algorithms powering the Acosign audio fingerprinting and recognition engine.

## Overview

Acosign is an audio identification and Content ID platform built on landmark constellation fingerprinting and temporal offset voting (inspired by the Dejavu algorithm). The system operates across four stages:

1. **Upload:** Audio is ingested via file upload or raw byte streams (supporting WAV, MP3, and other common formats).
2. **Fingerprint:** Raw audio is converted into a deterministic sequence of integer hashes representing time-frequency peak pairs.
3. **Store:** In the registration flow, hashes are indexed alongside track metadata and temporal timestamps (`hash`, `track_id`, `offset`).
4. **Identify:** Query clips are fingerprinted on the fly; retrieved candidate hashes cast alignment votes to determine the matching track, offset position, and confidence score.

## Fingerprint Pipeline

The fingerprinting engine converts continuous audio waveforms into compact, noise-tolerant landmarks through four sequential steps:

1. **Audio Ingestion & Resampling:** Signals are converted to mono float32 arrays resampled to a standardized 22,050 Hz. Audio under 1.0 second is rejected.
2. **Short-Time Fourier Transform (STFT):** A spectrogram is computed using an FFT window of `N_FFT = 4096` samples (~186 ms) and `HOP_LENGTH = 2048` samples (50% overlap). Magnitudes are converted to logarithmic decibels and normalized relative to the maximum amplitude clamped to an 80 dB dynamic range (`TOP_DB = 80.0`). This ensures invariant peak detection across loud and quiet copies of the same recording.
3. **2D Peak Detection:** Local maxima are identified using a 2D neighborhood filter with radius `PEAK_NEIGHBORHOOD_SIZE = 20` bins across frequency and time. Peaks below `MIN_AMPLITUDE = 10.0` dB above the noise floor are discarded. Results are sorted deterministically by time frame, then frequency bin.
4. **Landmark Pairing & 34-Bit Hash Packing:** Each anchor peak is paired with up to `FAN_OUT = 10` following target peaks whose time difference $\Delta t$ satisfies `MIN_DELTA_T <= Δt <= MAX_DELTA_T` (1 to 200 frames). Target peaks nearest in time are chosen first. Each pair is packed into a compact 34-bit integer:
   - `f1` (anchor frequency bin): 12 bits (values 0–4095)
   - `f2` (target frequency bin): 12 bits (values 0–4095)
   - `dt` (time-frame delta): 10 bits (values 0–1023)
   - Hash layout: `(f1 << 22) | (f2 << 10) | dt`

## Matching & Offset Voting

Candidate matching evaluates retrieved database hits against query clip hashes using temporal offset histogram voting:

$$\text{offset} = t_{\text{db}} - t_{\text{clip}}$$

For each candidate track, occurrences of each offset are tallied in a histogram. The track score is defined as the maximum count sharing a single offset frame.

### Why Offset Voting Beats Raw Hash Counting
Raw hash counting fails on short clips and dense music because common chords, harmonic overtones, or random acoustic collisions frequently produce false-positive hash hits across unrelated songs. 

Offset voting eliminates this vulnerability: coincidental hash collisions produce arbitrary, scattered time differences spread thinly across the time axis (offset counts rarely exceeding 1 or 2). Conversely, audio from the true track maintains a fixed temporal offset between query clip landmarks and database landmarks, causing dozens to hundreds of hashes to concentrate on the exact true alignment frame.

Matches are accepted only if `score >= MIN_MATCH_SCORE` (default 5). Ties between tracks are resolved deterministically by lowest `track_id`.

## Chosen Parameters

Following systematic grid evaluations across density and neighborhood tunables, the core parameters are configured as:

- `PEAK_NEIGHBORHOOD_SIZE = 20`
- `FAN_OUT = 10`
- `MIN_MATCH_SCORE = 5`
- `SAMPLE_RATE = 22050` Hz, `N_FFT = 4096`, `HOP_LENGTH = 2048`

For empirical benchmark matrices, accuracy percentages across noise levels, and trade-off comparisons with other configurations, see [Testing Documentation](testing.md).

## Known Limits

- **Heavy Acoustic Noise:** Under severe additive white noise at 10 dB SNR, identification accuracy on short 5-second clips degrades to ~76.7%, as background noise distorts local spectrogram maxima into altered frequency bins.
- **Single-Track Baseline Evaluation:** Benchmark metrics to date have been verified against real audio samples and synthetic validation suites; multi-million track scalability and collision profiling will be evaluated during the Phase 2 database integration.
