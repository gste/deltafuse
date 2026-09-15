# Pilot Evidence Index — J03 Document Flow Benchmark

**Qualification Card**: `J03-704`  
**Worker Profile**: `little-coder-0.83.0`  
**Core Agent**: `@earendil-works/pi-coding-agent@0.83.0`  
**Model Provider / ID**: `poolside` / `poolside/laguna-xs-2.1`  
**Attestation Status**: `measured` (offline preflight attestation verified)  
**Reservation Cap**: 32768 tokens  
**Context Window**: 131072 tokens  
**Date**: 2026-09-16  

---

## 1. Pilot Preflight & Attestation Summary

- **Harness & Worker Profile**:
  - Configuration pinned in `scripts/document_flow/worker/profile.json`.
  - Mode: `rpc` with flags `--offline`, `--no-session`, `--no-context-files`, `--no-skills`, `--no-extensions`.
- **Preflight Probes**:
  - Validated local adversarial boundary probes (`run_local_adversarial_probe`) ensuring no judge leaks, prompt injection immunity, and sealed sentinel filesystem boundaries.
  - Formatted sealed attestation document with framework SHA, wheel SHA256, and measured host parameters.

---

## 2. Pilot Run Execution & Evidence Chain

- **Pilot Run ID**: `pilot-run-001`
- **Execution Orchestration**: `scripts.document_flow.runner.execute_benchmark_run`
- **Evidence Structure**: Content-addressed append-only evidence store initialized at external run root (`events/`, `objects/`, `reports/`, `stages/`, `visits/`).
- **Lifecycle & Human Gates**: Evaluated stages with strict stage snapshots (`take_stage_snapshot`) and recorded stage visits.
- **Replay & Deterministic Evaluation**: Executed `reevaluate_run_from_store` verifying complete event chain, self-hash provenance, and failure classification.
