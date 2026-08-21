# Manuscript migration required for the v9 real-API experiment

This checklist applies to the marked LaTeX manuscript supplied on 20 August
2026. Existing numerical results are v8 results and must not be relabeled as
v9. Replace them only after the new oracle, replay, simulator, QPU, MI250X,
GH200, and B300 runs complete.

## Factual corrections required now

1. Replace every ICU claim. The ninth source is `openfda_adverse_events`, a
   frozen set of distinct FAERS adverse-event reports. It is pharmacovigilance
   data, not ICU telemetry, physiological monitoring, or a live clinical feed.
2. Replace the old source list with: OpenF1, Binance market data, NOAA SWPC,
   Open-Meteo, openFDA, NHL, OpenSky, OpenLigaDB, and MBTA.
3. Describe the data as real API records captured once and replayed as an
   ordered frozen stream. Do not claim the nine feeds were concurrently live.
4. State that all nine sources contain exactly 2,500 distinct source IDs and
   payload hashes. Cite snapshot SHA-256
   `7f93ef0b5ace3f42b3025ee36b169f515d2ac849d0082cd1509989312b05823d`.
5. Replace “six reconciliation routes and one/two abstention patterns” with an
   eight-route action space. `110` is `cross_encoder`; `111` is
   `cohere_embed_v4`. Confidence-based abstention is post-decoding and does
   not consume a bit pattern.
6. Replace “RealAmplitudes ansatz” where it describes the canonical circuit.
   The v9 circuit uses two repetitions of data re-uploading with parameterized
   `Ry` rotations and a fixed degree-three CNOT tree over 10 feature plus 3
   output qubits.
7. The Qwen chaos family is now model-backed. Qwen runs once on LUMI-G to
   produce validated one-to-one semantic key renames. Those saved drifted
   payloads—not new generations—are replayed on all hardware.

## Tables and numbers that must be regenerated

- Reconciler specification and route-bit mapping tables.
- Dataset/domain table and every per-domain accuracy table.
- Dispatch/route-selection distributions, including the held-out sample size.
- Logistic Regression, Random Forest, VQC simulator, hybrid, IBM, and VLQ
  selection metrics.
- CPU/GPU/cloud dispatch percentages and resource-use claims.
- MI250X one-card and four-card comparisons.
- GH200 and B300 comparisons.
- Cohere route and independent-baseline tables.
- Confidence intervals, LOAO results, Wilcoxon/Friedman tests, effect sizes,
  and multiple-comparison corrections.
- Energy, carbon, latency, throughput, and end-to-end accuracy values.

The prior `N=236` held-out value and all six-class confusion matrices are
invalid under v9. The correct held-out count must be read from the completed
v9 oracle manifest rather than estimated in prose.

## Suggested replacement dataset paragraph

> For multi-domain testing, 2,500 distinct records were captured from each of
> nine public APIs: OpenF1 car data, Binance market bars, NOAA SWPC solar-wind
> observations, Open-Meteo historical weather, openFDA FAERS adverse-event
> reports, NHL play-by-play events, OpenSky aircraft state vectors, OpenLigaDB
> football matches, and MBTA transit-stop records. The resulting 22,500-record
> snapshot was validated for unique source identifiers and payload hashes and
> then frozen for deterministic replay. The APIs were not contacted during
> hardware benchmarking. Consequently, the experiment evaluates a controlled
> replay of real API records rather than nine simultaneously active live
> feeds.

## Suggested replacement routing paragraph

> Three output qubits encode eight reconciliation actions: Levenshtein, regex,
> schema registry, MiniLM, Qwen2.5-1.5B, BGE, a cross-encoder, and Cohere Embed
> v4. Every bit pattern from `000` through `111` maps to one action. Optional
> abstention is applied after measurement when the maximum decoded class
> probability is below a declared threshold; it is not represented by a
> reserved quantum state.
