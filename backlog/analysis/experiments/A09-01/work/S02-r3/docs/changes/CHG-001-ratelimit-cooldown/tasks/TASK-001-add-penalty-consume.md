---
id: TASK-001
change: CHG-001-ratelimit-cooldown
slice: SLICE-01
kind: feature
status: pending
depends_on: []
requirement_delta: added
spec_refs:
  - docs/spec/security/ratelimit.md#REQ-RL-05
  - docs/spec/security/ratelimit.md#REQ-RL-02
design_ref: null
allowed_paths:
  - src/ratelimit/limiter.py
  - tests/test_limiter.py
forbidden_paths:
  - docs/spec/auth/**
---

## Outcome
When `TokenBucketLimiter` is constructed with `penalty_seconds > 0`, a failed
`consume` (insufficient tokens) transitions the key into a blocked state for
`penalty_seconds`, and every subsequent `consume` for that key returns `False`
immediately even if tokens have accumulated during the penalty window.

## References
- SLICE-01, CR-003, CR-004
- `docs/spec/security/ratelimit.md#REQ-RL-05` (added), `#REQ-RL-02` (modified)

## Steps
1. Confirm the existing per-key state tracking, token accumulation, and timing
   source in `src/ratelimit/limiter.py` (CR-008/CR-009); do not change baseline
   capacity/refill semantics.
2. Add the optional `penalty_seconds` constructor parameter (default `0.0`)
   without altering existing behavior when omitted.
3. On a failed `consume` when `penalty_seconds > 0`, record the key's blocked
   end time using the same timing source the limiter already uses.
4. At the top of `consume`, if the key is currently blocked, return `False`
   without deduction.

## Test oracle
`tests/test_limiter.py`: construct with `penalty_seconds > 0`, exhaust tokens,
assert the next `consume` returns `False` while blocked even after simulated
token accumulation, and returns `True` once the penalty window elapses.

## Unchanged behavior
Baseline limiter (no `penalty_seconds`) keeps prior rules exactly (CR-007);
capacity/refill and unknown-key defaults unchanged (REQ-RL-01/02/03).

## Verification
Run the limiter test suite for the new penalty path; ensure existing tests
still pass unchanged.
