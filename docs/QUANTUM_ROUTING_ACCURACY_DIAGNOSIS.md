# Quantum Routing Accuracy Diagnosis

This note summarizes why the current IBM QPU routing numbers are lower than the simulator results and what must be fixed before the router should be treated as paper-final.

## Executive Summary

The low IBM routing accuracy is not explained by hardware noise alone. The dominant issues are:

1. the training objective and the deployed inference circuit do not match exactly,
2. the training labels are derived from a different oracle than the packet-level evaluation used for reporting,
3. the drift generator includes many near no-op perturbations, which weakens supervision, and
4. the current circuit is deeper than it needs to be for a noisy device.

In other words, the present IBM result should be treated as a diagnostic run, not as evidence that the quantum routing idea itself has failed.

## Observed IBM Run-31 Metrics

The completed IBM hardware bundle in the repository shows:

- packet-level routing decision match: `45.79%`
- balanced accuracy: `33.58%`
- macro-F1: `33.32%`
- always-Levenshtein baseline: `51.14%`
- always-BERT baseline: `45.75%`

These numbers indicate that the deployed model is currently underperforming even simple classical baselines on the hardware evaluation set.

## Root Causes

### 1. Training / Inference Mismatch

The deployed router and the trainer are not solving the same classification problem.

- Inference uses a 10-feature input path with a 12-qubit layout where the first 10 qubits encode features and the last 2 qubits define the class decision.
- Training currently builds a different VQC objective with padded 12-dimensional inputs and a measurement interpretation that is not identical to the deployed inference path.

That means the saved weights are optimizing a different decision surface than the one used during runtime.

### 2. Label Oracle Mismatch

The current trainer assigns one label per `(api, chaos_method)` group from aggregate baseline results, while the benchmark evaluation is packet-level.

That creates a second mismatch:

- the training signal is coarse and aggregated,
- the evaluation target is per-packet,
- and the reported oracle for the hardware run expects reconcilers that are not represented consistently in the trainer.

This is a major reason the router can appear to "learn" one rule and then fail on the real packet stream.

### 3. Weak or No-Op Drift Samples

Some synthetic chaos variants do not materially change the packet content.

This reduces the separability of the classes and makes the router learn from ambiguous or nearly identical feature vectors. The result is a softer decision boundary and lower generalization quality.

### 4. Circuit Depth and Hardware Sensitivity

The current logical circuit is relatively deep for physical IBM hardware.

Even if the model objective were correct, the combination of entangling layers, transpilation overhead, and readout sensitivity will still reduce effective accuracy unless the circuit is simplified or hardware-aware mitigation is applied.

## What Should Change Before the Next Paper Run

1. Use one canonical routing objective for both training and inference.
2. Build a packet-level oracle dataset rather than an aggregate per-API label set.
3. Reject or resample no-op drift generations.
4. Persist the full trained bundle so the exact class interpretation is reproducible.
5. Validate on an ideal simulator first, then a noisy simulator, then IBM hardware.
6. Prefer a shallower circuit or a hierarchical router if the target class set expands.

## Paper-Safe Interpretation

The strongest defensible claim right now is that the router is a promising prototype whose accuracy is highly sensitive to the training/evaluation contract. The current IBM numbers should be presented as evidence of what breaks when that contract is violated, not as the final performance of the intended method.

## Short Version for the Manuscript

The observed drop in IBM QPU routing accuracy is primarily caused by a mismatch between the training objective and the deployed inference circuit, combined with packet-level evaluation against labels that were generated from a coarser aggregate oracle. Additional degradation comes from no-op drift samples and the depth of the physical circuit. The current hardware result should therefore be treated as a diagnostic baseline, not the final model quality.
