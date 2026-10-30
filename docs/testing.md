# Testing Documentation

This document details the test suites, verification methodologies, and accuracy evaluations for the Acosign fingerprinting engine.

## Engine evaluation

- **Tracks evaluated:** 3
- **Start positions per length:** 5 (10%, 30%, 50%, 70%, 85%)
- **False positives:** 0 / 270 queries (expected: 0)

| Variant | 3s Clip Acc (Med Score) | 5s Clip Acc (Med Score) | 10s Clip Acc (Med Score) |
|:---|:---:|:---:|:---:|
| **clean** | 80.0% (95) | 86.7% (532) | 93.3% (1025) |
| **noise_20db** | 73.3% (41) | 93.3% (118) | 93.3% (153) |
| **noise_10db** | 53.3% (19) | 93.3% (61) | 100.0% (62) |
| **noise_5db** | 33.3% (7) | 86.7% (23) | 93.3% (35) |
| **volume_0.3x** | 80.0% (95) | 86.7% (532) | 93.3% (1025) |
| **lowpass_8khz** | 80.0% (31) | 93.3% (88) | 100.0% (333) |

