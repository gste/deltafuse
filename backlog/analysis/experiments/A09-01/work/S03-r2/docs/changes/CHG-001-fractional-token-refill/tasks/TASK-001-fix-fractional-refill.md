---
id: TASK-001
change: CHG-001-fractional-token-refill
slice: SLICE-01
kind: bugfix
status: pending
depends_on: []
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md#REQ-RL-01
design_ref: null
allowed_paths:
  - src/ratelimit/limiter.py
  - tests/test_limiter.py
forbidden_paths:
  - docs/spec/**
---

## Outcome

`TokenBucketLimiter` preserves fractional token balances across calls, verified by a failing-then-passing Red test at small time intervals.

## Context

Bugfix slice SLICE-01. Reproduction: `TokenBucketLimiter(capacity=10, refill_rate=0.5)` after 3s restores 1 token instead of 1.5 because refill uses integer division `int(elapsed * refill_rate)`, discarding the fractional remainder between calls.

## Requirements

- `docs/spec/security/ratelimit.md#REQ-RL-01`: tokens refilled proportionally to elapsed time, preserving fractional balances.

## Dependencies

None.

## Test oracle

- Red first: a test asserting fractional accrual at a small interval (e.g. 0.5s at refill_rate 0.5 → 0.25 tokens) fails against current integer-division refill.
- After fix: accrual equals expected float within tolerance.

## Unchanged behavior

- `docs/spec/security/ratelimit.md` MUST remain unchanged (CR-005).
- `capacity > 0`, `refill_rate >= 0` invariants; unknown keys start at full capacity; `is_blocked` returns False baseline.

## Allowed / forbidden

- Allowed: `src/ratelimit/limiter.py`, `tests/test_limiter.py`.
- Forbidden: `docs/spec/**` (no normative spec edit).

## Verification

- Run the reproduction test (Red), then the fix, then full suite: `pytest tests/test_limiter.py -v`.
