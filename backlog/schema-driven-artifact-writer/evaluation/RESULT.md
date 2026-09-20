# Paired Small-Model Evaluation & Qualification Results

## Executive Summary

- **Evaluation Mode:** `paired_model` (Paired Small-Model Evaluation)
- **External Model Status:** `live_run_executed_2026-09-20_delivery_verified`
- **Acceptance Status:** `open_for_AW-20`
- **Total Harness Corpus Cases Evaluated:** 8 cases across 8 strata.
- **Harness Invariant Rates:** First-Pass Valid Rate: 100.0% (8/8), Semantic Correctness: 100.0% (8/8).
- **Live Paired Small-Model Run (2026-09-20):** executed on `inclusionai/ling-3.0-flash-fin:free` via the local `little-coder` CLI under the AMEND-3 delivery-verified transport (node-direct, neutral cwd, per-call observability byte-verification; 28/28 traces delivery-verified). Arm A (manual raw YAML): first-pass/semantic 25.0% (2/8, 95% CI 3.19–65.09), 12 mechanical retries. Arm B (typed Writer): first-pass/semantic 100.0% (8/8, 95% CI 63.06–100), 0 retries, forbidden gate blocked 1/1. Exploratory (n=8/arm); no general model-gain claim. Raw traces and protocol: `live-run-2026-09-20/`.

---

## Harness Invariant & Oracle Breakdown

| Case ID | Stratum | Operation | Expected Valid | First Pass | Semantic Correct | Gate Scope | Gate Check Status |
|---|---|---|---|---|---|---|---|
| `CASE-01` | `task_create` | `create` | `true` | `true` | `true` | `decomposed` | Evaluated |
| `CASE-02` | `routing_update` | `update` | `true` | `true` | `true` | `analyzed` | Evaluated |
| `CASE-03` | `spec_delta` | `create` | `true` | `true` | `true` | `specified` | Evaluated |
| `CASE-04` | `nested_patch` | `update` | `true` | `true` | `true` | `decomposed` | Evaluated |
| `CASE-05` | `explicit_removal` | `update` | `false` | `true` | `true` | `decomposed` | Rejection verified |
| `CASE-06` | `legacy_comments` | `update` | `true` | `true` | `true` | `analyzed` | Evaluated |
| `CASE-07` | `semantic_omission` | `create` | `false` | `true` | `true` | `decomposed` | Rejection verified |
| `CASE-08` | `unauthorized_status` | `update` | `false` | `true` | `true` | `decomposed` | Core-owned blocked |

---

## Status & Qualification Notes

1. **Withdrawal of Prior Synthetic Scores:**
   Historical reports asserting fixed manual-arm metrics (e.g. 62.5% vs 100%, 100% retry reduction) were synthetic and have been withdrawn.

2. **Negative Controls & Invariant Testing:**
   Evaluation harness and independent oracle verify ground-truth disk state and Core gate validation without trusting service return values. Empty-corpus and missing-endpoint executions correctly report `open_for_AW-20` and refuse synthetic qualification.

3. **Status for Final Backlog Reconciliation:**
   Live paired model sessions now exist with real model identity and
   delivery-verified traces (2026-09-20, AMEND-3 transport); the earlier
   `unavailable_no_endpoint` and "endpoint unsuitable" dispositions are
   superseded. Final closure remains with AW-42 reconciliation and AW-20.
