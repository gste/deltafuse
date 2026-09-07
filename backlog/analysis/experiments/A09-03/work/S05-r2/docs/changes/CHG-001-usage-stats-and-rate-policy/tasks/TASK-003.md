---
id: TASK-003
change: CHG-001-usage-stats-and-rate-policy
slice: SLICE-01
kind: feature
status: pending
depends_on:
  - TASK-001
  - TASK-002
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - tests
forbidden_paths: []
---

# TASK-003 — Integration test: usage stats + auto-block interaction

## Outcome
An integration test verifies that stats correctly reflect denials caused by both
token shortage and policy-based blocking while a key is auto-blocked (CR-003,
CR-004).

## Traceability
- Change/slice: CHG-001-usage-stats-and-rate-policy / SLICE-01
- Requirement: REQ-RL-05, REQ-RL-06 (behavior under test)
- Claim: CR-003, CR-004

## Steps
1. Write an integration test in `tests` exercising a single key through:
   - a run of token-shortage denials (assert `denied` increments, tokens
     unchanged),
   - crossing the consecutive-denial threshold to trigger auto-block,
   - blocked `consume` calls (assert `False`, no token deduction,
     `blocked_until` present in stats),
   - a successful `consume` after block expiry (assert counter reset and
     `success` increments).
2. Assert `get_stats(key)` totals are consistent across all phases.

## Test oracle
- Final `get_stats(key)` shows: `total` == all consume calls, `denied` ==
  token-shortage denials + block denials, `success` == successful consumes,
  `blocked_until` present during blocked window, and `peak_1s_load` reflects the
  busiest single second.

## Unchanged behavior
- REQ-RL-01/02/03/04 baseline preserved; test must not depend on unspecified
  schema keys beyond the four documented values.

## Allowed / forbidden
- Allowed: `tests` only.
- Forbidden: modifying production code in `src/ratelimit` in this task.

## Verification
- Run the integration test; it must pass deterministically (control time or use
  explicit thresholds/durations rather than real wall-clock sleeps).
