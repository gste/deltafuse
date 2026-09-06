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

# TASK-001 Fix fractional token refill accumulation and consume debit

## Outcome
`TokenBucketLimiter` accumulates pending tokens as `float` and debits integer or fractional tokens correctly, so proportional refill preserves fractional balances across calls.

## Context
`TokenBucketLimiter` currently uses integer division `int(elapsed * refill_rate)` in refill, discarding fractional accrual. With `capacity=10, refill_rate=0.5`, after 3s only 1 token is restored instead of 1.5. Fix lives in `src/ratelimit/limiter.py`; verify with `tests/test_limiter.py`.

## Requirements
- Refill must accumulate pending tokens as `float` so fractional parts persist between consecutive calls (CR-003).
- `consume(key, tokens)` must return True and deduct tokens when enough exist, else False without deduction, for integer and fractional token amounts (CR-004).
- Refill must never exceed capacity.

## Test oracle
With `TokenBucketLimiter(capacity=10, refill_rate=0.5)`, after 3s of waiting, pending tokens == 1.5 (float). `consume(key, 1.5)` returns True and leaves 8.5; `consume(key, 100)` returns False and leaves balance unchanged. Run: `python -m pytest tests/test_limiter.py -v`.

## Unchanged behavior
- REQ-RL-03 (unknown keys start at full capacity) and REQ-RL-04 (`is_blocked` returns False) are unaffected.
- `docs/spec/security/ratelimit.md` must NOT be modified.

## Allowed / forbidden
- Allowed: `src/ratelimit/limiter.py`, `tests/test_limiter.py`
- Forbidden: `docs/spec/**`

## Verification
`python -m pytest tests/test_limiter.py -v` must pass with the float-accumulation fix and the fractional-accrual reproduction test.
