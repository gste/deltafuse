---
id: TASK-002
change: CHG-001-ratelimit-cooldown
slice: SLICE-01
kind: feature
status: pending
depends_on:
  - TASK-001
requirement_delta: added
spec_refs:
  - docs/spec/security/ratelimit.md#REQ-RL-05
  - docs/spec/security/ratelimit.md#REQ-RL-06
design_ref: null
allowed_paths:
  - src/ratelimit/limiter.py
  - tests/test_limiter.py
forbidden_paths:
  - docs/spec/auth/**
---

## Outcome

`TokenBucketLimiter` implements the optional cooldown penalty per REQ-RL-05 and
REQ-RL-06, and `tests/test_limiter.py` verifies it.

## Steps

- Add an optional `penalty_seconds` init parameter defaulting to `0.0`.
- On a failed `consume` (insufficient tokens) when `penalty_seconds > 0`, store
  a blocked timestamp for the key lasting `penalty_seconds`.
- At the start of `consume`, if the key is blocked, return `False` immediately
  even if tokens have accumulated; lift the block on the next request once
  `penalty_seconds` has elapsed, then resume normal logic.
- Implement `is_blocked(key)` to return `True` while under penalty and `False`
  otherwise (REQ-RL-06).
- Preserve baseline behavior when `penalty_seconds` is absent (REQ-RL-04, REQ-RL-07).

## Test oracle

`tests/test_limiter.py` must assert: (1) a failed consume with `penalty_seconds > 0`
blocks subsequent consumes returning `False` even after token accrual; (2) after
`penalty_seconds` elapses the next `consume` resumes normal logic; (3)
`is_blocked(key)` returns `True` during penalty and `False` otherwise; (4) the
baseline limiter with no `penalty_seconds` keeps prior behavior.

## Unchanged behavior

- REQ-RL-01 (capacity > 0, refill_rate >= 0), REQ-RL-02, REQ-RL-03, and the
  baseline `is_blocked` (REQ-RL-04) behavior are preserved.

## Verification

- Run the limiter test suite and confirm all new and existing tests pass.

---

## Scope

- In scope: `src/ratelimit/limiter.py` and `tests/test_limiter.py` only.
- Out of scope: capacity/refill semantics (REQ-RL-01/02/03), unknown-key handling,
  and any non-`security.ratelimit` callers.
