---
id: TASK-001
change: CHG-001-ratelimit-cooldown
slice: SLICE-01
kind: feature
status: pending
depends_on: []
requirement_delta: added
spec_refs:
  - docs/spec/security/ratelimit.md#REQ-RL-01
  - docs/spec/security/ratelimit.md#REQ-RL-04
design_ref: null
allowed_paths:
  - src/ratelimit/limiter.py
  - tests/test_limiter.py
forbidden_paths:
  - docs/spec/auth/**
---

# TASK-001 — Optional `penalty_seconds` init param + baseline `is_blocked`

## Outcome
`TokenBucketLimiter` accepts an optional `penalty_seconds` parameter defaulting to `0.0`, and `is_blocked(key)` returns `False` for the baseline limiter (no penalty lock).

## References
- Change/slice: CHG-001-ratelimit-cooldown / SLICE-01
- `docs/spec/security/ratelimit.md#REQ-RL-01` (accepts `penalty_seconds` default `0.0`)
- `docs/spec/security/ratelimit.md#REQ-RL-04` (`is_blocked` returns `False` baseline)

## Test oracle
- `TokenBucketLimiter()` constructs without `penalty_seconds` and `is_blocked(any_key)` returns `False`.
- `TokenBucketLimiter(penalty_seconds=0.0)` behaves identically to the no-arg constructor.
- A `consume` with sufficient tokens still returns `True` and deducts; insufficient returns `False` without deduction (REQ-RL-02).

## Unchanged behavior
- Capacity/refill semantics, unknown-key full-capacity start (REQ-RL-03), and existing `consume` contract must remain intact.

## Allowed / forbidden
- Allowed: `src/ratelimit/limiter.py`, `tests/test_limiter.py`
- Forbidden: `docs/spec/auth/**`

## Verification
- Run the limiter test suite (e.g. `pytest tests/test_limiter.py`) and confirm all baseline cases pass.
