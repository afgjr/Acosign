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

## Chosen parameters

- **PEAK_NEIGHBORHOOD_SIZE:** `20`
- **FAN_OUT:** `10`

### Parameter sweep comparison

| (PEAK_NEIGHBORHOOD_SIZE, FAN_OUT) | Hashes/sec | Clean 5s Acc | Noise 10dB 5s Acc | Lowpass 5s Acc | False Positives |
|:---|:---:|:---:|:---:|:---:|:---:|
| **(20, 5) baseline** | 134.2 | 90.0% | 70.0% | 80.0% | 0 |
| **(20, 10)** | 268.2 | 100.0% | 76.7% | 90.0% | 0 |
| **(15, 5)** | 222.5 | 80.0% | 66.7% | 60.0% | 0 |
| **(15, 8)** | 355.9 | 90.0% | 76.7% | 80.0% | 0 |
| **(12, 10)** | 600.3 | 80.0% | 70.0% | 80.0% | 0 |

Under heavy background noise (SNR 10 dB), short 5-second clips achieve ~77% identification accuracy, representing the primary operational limitation in degraded acoustic environments.

