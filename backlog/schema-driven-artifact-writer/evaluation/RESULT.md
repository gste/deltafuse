# Paired Small-Model Evaluation & Qualification Results

## Executive Summary

- **Evaluation Mode:** `paired_model` (Paired Small-Model Evaluation)
- **External Model Status:** `unavailable_no_endpoint`
- **Acceptance Status:** `open_for_AW-20`
- **Total Harness Corpus Cases Evaluated:** 8 cases across 8 strata.
- **Harness Invariant Rates:** First-Pass Valid Rate: 100.0% (8/8), Semantic Correctness: 100.0% (8/8).
- **Live Endpoint Assessment:** External paired small-model endpoint is unavailable in the execution environment; live paired evaluations (Arm A manual YAML vs Arm B typed Writer) have not been run against a live endpoint. Acceptance remains open for AW-20 without synthetic substitution.

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
   Paired model acceptance remains `open_for_AW-20` pending live endpoint execution.
