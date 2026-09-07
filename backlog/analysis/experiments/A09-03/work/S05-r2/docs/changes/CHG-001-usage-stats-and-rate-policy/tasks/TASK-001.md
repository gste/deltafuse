---
id: TASK-001
change: CHG-001-usage-stats-and-rate-policy
slice: SLICE-01
kind: feature
status: pending
depends_on: []
requirement_delta: added
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - src/ratelimit
forbidden_paths: []
---

# TASK-001 — Per-key usage stats tracking

## Outcome
`get_stats(key)` returns a dict with at least `total`, `success`, `denied`, and
`peak_1s_load` for any key, counting denials from both token shortage and
policy-based blocking (REQ-RL-05).

## Traceability
- Change/slice: CHG-001-usage-stats-and-rate-policy / SLICE-01
- Requirement: REQ-RL-05 (added by this Change)
- Claim: CR-001

## Steps
1. Locate the `consume` code path in `src/ratelimit` (see capability `code_roots`).
2. In `consume`, increment a per-key `total` counter on every call.
3. Increment `success` when `consume` returns `True`; increment `denied` when it
   returns `False` (token shortage OR policy block).
4. Track per-key peak 1-second load: bucket calls by integer second and record
   the max bucket size observed for that key.
5. Implement `get_stats(key)` returning `{total, success, denied, peak_1s_load}`.
6. Ensure unknown keys return zeroed stats without raising.

## Test oracle
- Call `consume` N times for a key with enough tokens, then enough denials;
  assert `get_stats(key)` reports correct `total`, `success`, `denied`, and that
  `peak_1s_load` equals the max calls within any single second.
- A denial caused by policy block increments `denied` (not a token deduction).

## Unchanged behavior
- REQ-RL-01/02/03/04 baseline: capacity/refill, consume contract, unknown-key
  start full, `is_blocked` returns `False` for baseline limiter.
- Stats tracking must not alter token deduction or return values.

## Allowed / forbidden
- Allowed: `src/ratelimit` only.
- Forbidden: modifying `consume` semantics, capacity/refill, or `is_blocked`.

## Verification
- Run the integration/unit test suite for the ratelimit package after writing tests.
- Confirm `get_stats` values match expected counts in the oracle scenario.
