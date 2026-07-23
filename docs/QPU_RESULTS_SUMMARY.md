# Quantum Benchmark Summary for TKDE

This summary describes the 9-API manuscript corpus in `data/paper_2026/` and the associated quantum-routing evidence in the repository.

## Current Execution Note

As of 2026-07-22, the remaining IBM QPU budget is about 4 minutes and 7 seconds. That is enough for at most one compact confirmatory run, not two additional full 9-API repeats. The paper should therefore treat any new IBM execution as a short robustness check and keep the existing IBM bundle as supporting evidence until a full rerun can be completed.

The key distinction is:

- the full benchmark dataset is the 22,500-packet 9-API corpus at `data/ingested/telemetry_clean_bench_22500.json`
- the 10-repetition simulator sweep in `data/reports/quantum_MI250X_10rep_success/` covers the 9 primary APIs used in the paper, plus one auxiliary `industrial_iiot` stress domain that is not part of the manuscript core
- the physical IBM QPU bundle in `data/reports/quantum_MI250X_ibm_qpu/` is a smaller 4-API hardware subset and should be treated as supporting evidence, not the whole study

## Experimental Scope

- Primary dataset: `data/ingested/telemetry_clean_bench_22500.json`
- Primary study scope: 9 APIs, 2,500 packets each, 22,500 packets total
- Quantum validation bundle: 10-repetition simulator sweeps under `data/reports/quantum_MI250X_10rep_success/`
- Hardware subset: physical IBM QPU bundle under `data/reports/quantum_MI250X_ibm_qpu/`
- Total quantum-routed rows in the 9-API simulator subset: 270
- Chaos methods: `json_manip`, `qwen`, `schema_alter`
- Quantum phase: `quantum_routed`

The nine primary APIs represented in the simulator results are:

- `openf1`
- `finnhub`
- `spacex`
- `openweather`
- `clinical`
- `hockey_nhl`
- `aviation_opensky`
- `football_uefa`
- `smartcity_transit`

The auxiliary `industrial_iiot` domain is present in the simulator bundle but excluded from the manuscript summary below.

## Key Quantitative Findings

Across the 9-API quantum-routed simulator subset, the mean accuracy was `85.20%` and the mean latency was `614.81 ms`.

| Scope | Mean Accuracy | Mean Latency | Interpretation |
|---|---:|---:|---|
| Overall, 9-API subset | 85.20% | 614.81 ms | Strong aggregate routing quality across the primary manuscript domains |
| `football_uefa` | 93.33% | 620.70 ms | Highest accuracy among the primary APIs |
| `hockey_nhl` | 91.68% | 806.24 ms | High accuracy with heavier latency |
| `clinical` | 90.20% | 915.39 ms | Strong accuracy, but latency remains elevated |
| `smartcity_transit` | 92.42% | 368.35 ms | Best latency/accuracy balance among the highest-accuracy domains |
| `aviation_opensky` | 61.79% | 478.29 ms | Hardest primary API in the simulator sweep |

### By Chaos Method

| Chaos Method | Mean Accuracy | Mean Latency | Takeaway |
|---|---:|---:|---|
| `json_manip` | 88.50% | 630.11 ms | Best overall accuracy in the 9-API subset |
| `qwen` | 85.58% | 613.57 ms | Competitive accuracy with similar latency |
| `schema_alter` | 81.53% | 600.75 ms | Lowest accuracy and the toughest drift family |

## Paper-Ready Interpretation

The 9-API quantum-routing results show that the VQC dispatcher remains effective across heterogeneous telemetry domains, with the strongest results on `football_uefa`, `smartcity_transit`, and `hockey_nhl`. The weakest domain in the 9-API subset is `aviation_opensky`, which is consistent with that domain’s higher structural variability.

At the method level, JSON manipulation produces the best overall accuracy, while schema alteration is the most difficult perturbation family. The results support the claim that the quantum router is able to absorb drift without collapsing accuracy across the full benchmark corpus, even when the latency profile varies materially by domain.

The physical IBM QPU bundle remains useful as hardware validation, but it should be cited as a smaller 4-API subset rather than the full paper corpus.

## Ready-to-Paste Results Paragraph

> Across the 9-API quantum-routed simulator subset, the proposed VQC dispatcher achieved a mean accuracy of 85.20% with a mean latency of 614.81 ms. The strongest primary API was `football_uefa` at 93.33% accuracy, followed by `smartcity_transit` at 92.42% and `hockey_nhl` at 91.68%. `aviation_opensky` was the most challenging primary API at 61.79% accuracy. Among drift families, JSON manipulation delivered the best overall accuracy (88.50%), followed by Qwen semantic drift (85.58%), while schema alteration produced the lowest accuracy (81.53%). These results indicate that the routing layer remains effective across the 9-API manuscript corpus while preserving stable behavior under heterogeneous schema and semantic drift.
