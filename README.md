# Semantic Drift Evaluation Pipeline

This repository benchmarks semantic drift detection and repair under controlled chaos injection. The summaries below are generated directly from combined_results.json (9,900 rows) and are ordered to move from hardware-level behavior to strategy effects, decoder coverage, hardware/strategy interactions, and the final findings narrative.

## Data Scope
- 9 normalized hardware platforms are represented in the merged export.
- The merged file contains json, gemma, and schema chaos strategies; the strategy matrix below focuses on json vs gemma to match the requested comparison.
- All rows in combined_results.json record reconciliation_winner = canonical and fallback_used = False, so the decoder section is a limitation report rather than a decoder ranking.
- Semantic drift ratio treats value_contradiction as semantic and all other drift flags as structural.

## 1. Hardware-Level Summary Matrix

| Hardware | Performance Metrics | Drift & Chaos Metrics | Resilience & Repair Metrics | Stability Metrics | Notes |
| --- | --- | --- | --- | --- | --- |
| GH200_141GB | p95 7.69 ms; throughput 196.25 pps; bytes/s 2.03e+10; timing 7,693 µs; runtime 0.007693 s | drift 87.5%; top missing_keys 27.5%, extra_keys 22.3%, nested_corruption 12.5%; chaos json 34.5%, gemma 32.7%, schema 32.7%; levels low 34.5%, high 32.7%, medium 32.7% | repair 0.88; recovery 0.98; resilience P/P2 0.74/0.76; winner canonical 100.0% | var p95 18.95; var pps 20,779.50; var recovery 0.000467 | Sub-10 ms latency profile; Highest resilience tier |
| NVIDIA_H200_140GB | p95 8.59 ms; throughput 163.99 pps; bytes/s 1.07e+10; timing 8,586 µs; runtime 0.008586 s | drift 87.7%; top missing_keys 25.8%, extra_keys 24.5%, nested_corruption 11.5%; chaos json 34.5%, gemma 32.7%, schema 32.7%; levels low 34.5%, high 32.7%, medium 32.7% | repair 0.88; recovery 0.98; resilience P/P2 0.73/0.76; winner canonical 100.0% | var p95 17.63; var pps 13,485.70; var recovery 0.000471 | Sub-10 ms latency profile; Highest resilience tier |
| NVIDIA_H100_80GB_HBM3_80GB | p95 14.55 ms; throughput 177.66 pps; bytes/s 1.22e+10; timing 14,553 µs; runtime 0.014553 s | drift 87.4%; top missing_keys 27.1%, extra_keys 23.4%, nested_corruption 11.3%; chaos json 34.5%, gemma 32.7%, schema 32.7%; levels low 34.5%, high 32.7%, medium 32.7% | repair 0.87; recovery 0.98; resilience P/P2 0.71/0.74; winner canonical 100.0% | var p95 404.27; var pps 25,948.84; var recovery 0.000456 | Highest resilience tier |
| NVIDIA_GeForce_RTX_5090 | p95 23.88 ms; throughput 115.97 pps; bytes/s 1.19e+10; timing 23,877 µs; runtime 0.023877 s | drift 86.5%; top missing_keys 28.2%, extra_keys 22.1%, nested_corruption 10.8%; chaos json 34.5%, gemma 32.7%, schema 32.7%; levels low 34.5%, high 32.7%, medium 32.7% | repair 0.86; recovery 0.98; resilience P/P2 0.64/0.69; winner canonical 100.0% | var p95 566.11; var pps 14,456.34; var recovery 0.000509 | Mid-band latency / resilience profile |
| NVIDIA_B300_SXM6_AC_262GB | p95 25.82 ms; throughput 51.28 pps; bytes/s 2.98e+10; timing 25,818 µs; runtime 0.025818 s | drift 85.4%; top missing_keys 24.3%, extra_keys 20.2%, nested_corruption 14.4%; chaos json 34.5%, gemma 32.7%, schema 32.7%; levels low 34.5%, high 32.7%, medium 32.7% | repair 0.85; recovery 0.98; resilience P/P2 0.58/0.64; winner canonical 100.0% | var p95 38,057.26; var pps 58.70; var recovery 0.000834 | Mid-band latency / resilience profile |
| NVIDIA_B200_178GB | p95 33.90 ms; throughput 36.96 pps; bytes/s 2.07e+10; timing 33,897 µs; runtime 0.033897 s | drift 88.0%; top missing_keys 27.3%, extra_keys 20.7%, nested_corruption 12.2%; chaos json 34.5%, gemma 32.7%, schema 32.7%; levels low 34.5%, high 32.7%, medium 32.7% | repair 0.88; recovery 0.98; resilience P/P2 0.54/0.60; winner canonical 100.0% | var p95 2,123.57; var pps 70.34; var recovery 0.000957 | Mid-band latency / resilience profile |
| RTX 6000 Workstation_96GB | p95 35.62 ms; throughput 64.58 pps; bytes/s 1.16e+10; timing 35,623 µs; runtime 0.035623 s | drift 85.9%; top missing_keys 28.6%, extra_keys 22.1%, nested_corruption 11.6%; chaos json 34.5%, gemma 32.7%, schema 32.7%; levels low 34.5%, high 32.7%, medium 32.7% | repair 0.86; recovery 0.98; resilience P/P2 0.59/0.65; winner canonical 100.0% | var p95 978.43; var pps 3,142.75; var recovery 0.000518 | Mid-band latency / resilience profile |
| Apple_M4_16GB | p95 207.98 ms; throughput 4.86 pps; bytes/s 9.54e+09; timing 207,984 µs; runtime 0.207984 s | drift 86.8%; top missing_keys 27.0%, extra_keys 21.3%, nested_corruption 10.7%; chaos json 34.5%, gemma 32.7%, schema 32.7%; levels low 34.5%, high 32.7%, medium 32.7% | repair 0.87; recovery 0.98; resilience P/P2 0.43/0.52; winner canonical 100.0% | var p95 501.69; var pps 0.27; var recovery 0.000855 | High-latency profile; Lower resilience tier |
| AMD_Radeon_RX_7900_XT_20GB | p95 538.42 ms; throughput 9.62 pps; bytes/s 2.00e+10; timing 538,415 µs; runtime 0.538415 s | drift 84.6%; top missing_keys 24.0%, extra_keys 20.1%, nested_corruption 13.1%; chaos json 34.5%, gemma 32.7%, schema 32.7%; levels low 34.5%, high 32.7%, medium 32.7% | repair 0.85; recovery 0.98; resilience P/P2 0.44/0.52; winner canonical 100.0% | var p95 446,432.66; var pps 39.49; var recovery 0.000872 | High-latency profile; Lower resilience tier |

Across hardware, the biggest separations are latency and resilience rather than raw drift frequency. GH200_141GB and NVIDIA_H200_140GB are the clear leaders on both fronts, H100 and the larger datacenter GPUs remain strong, and the AMD and Apple systems are the slowest while also sitting in the lower resilience tier. Drift rates stay in a fairly tight band, which suggests the hardware mainly changes how costly recovery is, not whether drift appears at all.

## 2. Chaos-Strategy Summary Matrix (JSON vs GEMMA)

Schema rows are present in the merged export, but this matrix focuses on json and gemma because those are the two adversarial strategies requested for the comparison.

| Chaos Strategy | Drift Profile | Performance Impact | Resilience | Chaos Severity | Key Observations |
| --- | --- | --- | --- | --- | --- |
| json | freqs missing_keys 26.9%, extra_keys 20.6%, split_fields 12.0%, type_mismatch 8.4%, merged_fields 11.8%, renamed_keys 8.0%, value_contradiction 7.8%, nested_corruption 11.5%; avg drift_type_count 1.07; sem/struct ratio 0.079 | p95 45.58 ms; throughput 121.14 pps; slowdown vs baseline 1.01x | repair 0.91; recovery 0.98; winner canonical 100.0% | low 36.8%; medium 31.6%; high 31.6% | JSON stays near baseline; Gemma is far slower but slightly more repair-forward |
| gemma | freqs extra_keys 33.7%, missing_keys 32.4%, nested_corruption 12.9%, type_mismatch 8.4%, value_contradiction 9.1%, merged_fields 12.1%, split_fields 7.8%; avg drift_type_count 1.16; sem/struct ratio 0.085 | p95 215.18 ms; throughput 39.17 pps; slowdown vs baseline 4.75x | repair 0.96; recovery 0.98; winner canonical 100.0% | low 33.3%; medium 33.3%; high 33.3% | Gemma produces the heaviest latency tax while preserving strong repair rates |

JSON mutation stays closest to baseline behavior: it is fast, has the lowest slowdown factor, and maintains the strongest overall recovery score at a slightly lower repair rate than Gemma. Gemma chaos is much more expensive in latency terms—roughly a 4.75x slowdown versus baseline rows—but it is also the more repair-forward strategy, with the highest mean repair rate and only a small drop in recovery score. The semantic/structural split is similar for both strategies, so the main difference is not drift composition alone; it is how much downstream work the repair path must absorb.

## 3. Decoder / Repair Engine Summary Matrix

The merged file does not retain per-decoder winner diversity: every row records canonical reconciliation, and the nested decoder latency fields are zeroed. This table therefore reports the observed canonical control outcome and marks the requested decoders as not recoverable from combined_results.json.

| Decoder | Observed Win Rate | Mean Repair Rate | Mean Recovery Score | Failure Modes | Recorded Latency | Latency Variance | Win by Chaos Strategy | Win by Chaos Level | Hardware Interaction | Strengths | Weaknesses |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| canonical (observed control) | 100.0% | 0.87 | 0.98 | No failures observed in merged file | 0.00 | 0.00 | json 34.5%; gemma 32.7%; schema 32.7% | low 34.5%; medium 32.7%; high 32.7% | all hardware (tie) | Only observed reconciliation outcome; stable canonical bypass | No decoder diversity recorded in combined_results.json |
| levenshtein | n/a | n/a | n/a | Not observable in combined_results.json | n/a | n/a | n/a | n/a | n/a | No decoder-specific wins recorded in merged file | Per-decoder attribution not retained |
| regex | n/a | n/a | n/a | Not observable in combined_results.json | n/a | n/a | n/a | n/a | n/a | No decoder-specific wins recorded in merged file | Per-decoder attribution not retained |
| bert | n/a | n/a | n/a | Not observable in combined_results.json | n/a | n/a | n/a | n/a | n/a | No decoder-specific wins recorded in merged file | Per-decoder attribution not retained |
| gemma | n/a | n/a | n/a | Not observable in combined_results.json | n/a | n/a | n/a | n/a | n/a | No decoder-specific wins recorded in merged file | Per-decoder attribution not retained |

Canonical is the only observed reconciliation outcome in the merged file, so decoder differentiation is not measurable here. The practical reading is that the current export validates the canonical bypass path, but it does not support a ranking among Levenshtein, regex, BERT, and Gemma repair engines. If that comparison matters for the paper, the source logging needs to retain per-decoder outcomes before aggregation.

## 4. Hardware × Chaos × Decoder Interaction Matrix

| Hardware | JSON | Gemma |
| --- | --- | --- |
| GH200_141GB | canonical; drift 90.8%; recovery 0.98; p95 4.98 ms; top drift missing_keys, extra_keys, split_fields | canonical; drift 96.9%; recovery 0.97; p95 13.18 ms; top drift extra_keys, missing_keys, nested_corruption |
| NVIDIA_H200_140GB | canonical; drift 89.7%; recovery 0.98; p95 6.21 ms; top drift missing_keys, extra_keys, nested_corruption | canonical; drift 97.5%; recovery 0.97; p95 13.29 ms; top drift extra_keys, missing_keys, nested_corruption |
| NVIDIA_H100_80GB_HBM3_80GB | canonical; drift 92.6%; recovery 0.98; p95 11.77 ms; top drift missing_keys, extra_keys, merged_fields | canonical; drift 96.4%; recovery 0.98; p95 19.44 ms; top drift extra_keys, missing_keys, nested_corruption |
| NVIDIA_GeForce_RTX_5090 | canonical; drift 91.3%; recovery 0.98; p95 8.82 ms; top drift missing_keys, extra_keys, split_fields | canonical; drift 95.6%; recovery 0.97; p95 54.33 ms; top drift missing_keys, extra_keys, merged_fields |
| NVIDIA_B300_SXM6_AC_262GB | canonical; drift 91.3%; recovery 0.98; p95 35.00 ms; top drift missing_keys, extra_keys, nested_corruption | canonical; drift 94.7%; recovery 0.98; p95 23.91 ms; top drift missing_keys, extra_keys, nested_corruption |
| NVIDIA_B200_178GB | canonical; drift 91.8%; recovery 0.98; p95 45.35 ms; top drift missing_keys, extra_keys, split_fields | canonical; drift 96.7%; recovery 0.98; p95 31.10 ms; top drift missing_keys, extra_keys, merged_fields |
| RTX 6000 Workstation_96GB | canonical; drift 91.6%; recovery 0.98; p95 14.15 ms; top drift missing_keys, extra_keys, split_fields | canonical; drift 95.3%; recovery 0.97; p95 79.54 ms; top drift extra_keys, missing_keys, nested_corruption |
| Apple_M4_16GB | canonical; drift 90.3%; recovery 0.98; p95 208.54 ms; top drift missing_keys, extra_keys, merged_fields | canonical; drift 96.9%; recovery 0.98; p95 208.02 ms; top drift extra_keys, missing_keys, merged_fields |
| AMD_Radeon_RX_7900_XT_20GB | canonical; drift 91.3%; recovery 0.98; p95 75.43 ms; top drift missing_keys, extra_keys, merged_fields | canonical; drift 94.7%; recovery 0.98; p95 1,493.85 ms; top drift missing_keys, extra_keys, nested_corruption |

- GH200_141GB and NVIDIA_H200_140GB keep drift recovery fast under both strategies, with canonical outcomes and low p95 latency even when Gemma chaos is applied.
- Gemma raises latency the most on AMD_Radeon_RX_7900_XT_20GB, NVIDIA_GeForce_RTX_5090, and RTX 6000 Workstation_96GB, showing that the slower systems pay the largest adversarial penalty.
- JSON chaos is consistently cheaper to handle than Gemma chaos, but the recovery score gap is small; the main difference is execution cost, not catastrophic repair collapse.
- Hardware differences are more visible in latency than in drift rate, which stays broadly similar across platforms and strategies.

## 5. Findings Summary
Across hardware, the dominant separation is not drift frequency but execution cost and resilience. The fastest platforms—GH200_141GB and NVIDIA_H200_140GB—stay in the single-digit millisecond range and also occupy the top resilience tier, while AMD_Radeon_RX_7900_XT_20GB and Apple_M4_16GB sit at the opposite end with much higher latency and lower resilience.
Chaos strategy changes behavior in a measurable way. JSON mutation remains close to baseline latency and produces a balanced structural-drift profile, whereas Gemma chaos raises latency sharply—especially on consumer and workstation-class systems—while also nudging the drift mix toward more extra/missing-key corruption.
The decoder picture in this merged file is intentionally simple: every row records canonical reconciliation and no fallback usage, so the file does not expose per-decoder winner diversity. That limitation matters for interpretation; this README therefore treats the decoder matrix as a coverage report rather than a competitive ranking.
Stability trends are favorable on the strongest hardware and more volatile on the slower platforms. Recovery scores remain tight across all systems, but p95 latency variance is much higher on the mid-range and consumer GPUs, showing that hardware mainly changes tail cost rather than the average ability to repair drift.

### Takeaways
- GH200_141GB and NVIDIA_H200_140GB provide the best combined latency/resilience profile.
- Gemma chaos is the most expensive strategy by latency, even when repair quality stays high.
- Drift-rate differences across hardware are modest; the larger separator is how much work the repair path must do.
- The merged file does not retain per-decoder competition, so decoder-level ranking should be repeated from richer logs if needed.

### Method Note
For the drift-profile ratios, the analysis treats value_contradiction as semantic drift and the remaining drift flags as structural drift. That convention keeps the ratio aligned with the question of whether the injected mutation changed meaning versus structure.
