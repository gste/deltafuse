# Campaign Evidence Index — J03 Document Flow Benchmark

**Qualification Card**: `J03-705`  
**Campaign ID**: `camp-J03-01`  
**Worker Model**: `poolside/laguna-xs-2.1`  
**Harness**: `little-coder-0.83.0`  
**Target Runs**: 3 preregistered runs (`run-01`, `run-02`, `run-03`)  
**Preregistered Seeds**: `42001`, `42002`, `42003`  
**Date**: 2026-09-16  

---

## 1. Campaign Integrity & Non-Cherry-Picking Invariant

- **Strict Member Invariant**:
  - The campaign plan mandates exactly 3 runs on fresh sessions, sandboxes, and volumes.
  - Any missing required run transitions the campaign to `incomplete` status and nullifies the numeric campaign score.
  - Any invalid member transitions the campaign to `invalid` status and nullifies the score.
  - Mutant M28 (`ABS.CAMPAIGN`) validates that dropping failed members or cherry-picking runs fails qualification.

---

## 2. Campaign Aggregation Arithmetic

- **Aggregation Formula**:
  $$\text{Campaign Score} = \text{round}\left(\frac{1}{2} \times \text{Median} + \frac{3}{10} \times \text{Minimum} + \frac{1}{5} \times \text{Mean}\right)$$
- **Exact Rational Evaluation**:
  - Computed using exact Python `Fraction` arithmetic and half-even rounding.
  - Verified across boundary conditions, perfect runs ($10000$), failed runs ($1$), and multi-run distributions with population variance.

---

## 3. Independent Replay & Comparison

- **Deterministic Disk Replay**:
  - `reevaluate_run_from_store` re-evaluates all 7 lifecycle stages and 4 system groups directly from disk artifacts.
  - Two repeated replays yield 100% byte-identical semantic result hashes.
- **Cross-Campaign Comparison**:
  - `compare_campaigns` enforces compatibility of profile, host, contract, registry, and variant identities before generating comparative stage deltas and overall score deltas.
