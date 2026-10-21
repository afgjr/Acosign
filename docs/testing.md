# Testing Documentation

This document details the test suites, verification methodologies, and accuracy evaluations for the Acosign fingerprinting engine.

## Engine evaluation

- **Tracks evaluated:** 1
- **Start positions per length:** 5 (10%, 30%, 50%, 70%, 85%)
- **False positives:** 0 / 90 queries (expected: 0)

| Variant | 3s Clip Acc (Med Score) | 5s Clip Acc (Med Score) | 10s Clip Acc (Med Score) |
|:---|:---:|:---:|:---:|
| **clean** | 100.0% (124) | 100.0% (208) | 100.0% (620) |
| **noise_20db** | 60.0% (13) | 80.0% (28) | 60.0% (60) |
| **noise_10db** | 60.0% (9) | 80.0% (16) | 80.0% (34) |
| **noise_5db** | 40.0% (5) | 80.0% (9) | 100.0% (19) |
| **volume_0.3x** | 100.0% (124) | 100.0% (208) | 100.0% (620) |
| **lowpass_8khz** | 100.0% (76) | 100.0% (135) | 80.0% (306) |

