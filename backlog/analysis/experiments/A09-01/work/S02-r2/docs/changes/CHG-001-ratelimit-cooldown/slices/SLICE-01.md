---
id: SLICE-01
change: CHG-001-ratelimit-cooldown
title: Optional cooldown penalty on TokenBucketLimiter.consume
status: analyzing
primary_capability: security.ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-001
  - CR-002
  - CR-003
depends_on: []
---

## Scope

- **In scope:** Add optional `penalty_seconds` (default `0.0`) to `TokenBucketLimiter`; on failed `consume`, lock the key for `penalty_seconds`; `is_blocked(key)` reflects lock state; auto-release after window; preserve baseline behavior (REQ-RL-01..04).
- **Out of scope:** Concurrency model for token accrual during lock (U3); public-vs-internal decision for `is_blocked` (U2) pending human Decision.

## Dependencies

- Requires confirming language/runtime and public API surface of `TokenBucketLimiter` (U1).

## Spec references

- `docs/spec/security/ratelimit.md`: REQ-RL-01 (capacity/refill), REQ-RL-02 (consume), REQ-RL-03 (unknown keys), REQ-RL-04 (`is_blocked` baseline).

## Unchanged behavior

- Baseline consume/refill semantics and unknown-key handling remain per REQ-RL-01..03.

## Risks

- U1/U2/U3 unresolved; penalty lock may interact with concurrent accrual (U3).

## Context budget

- max_tokens: 4000, max_files: 6.

## Deltas

- **spec:** add REQ-RL-05 (penalty lock) and REQ-RL-06 (auto-release); `operation: add`.
- **catalog:** `penalty_seconds` becomes part of `TokenBucketLimiter` contract; `operation: add`.
- **Decisions:** propose Decision on `is_blocked` visibility and concurrency handling; `operation: propose`.
- **tasks/tests/implementation/evidence:** to be decomposed after Decision convergence; `operation: pending`.
