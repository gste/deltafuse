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
  - docs/spec/security/ratelimit.md#REQ-RL-02
design_ref: null
allowed_paths:
  - src/ratelimit/limiter.py
  - tests/test_limiter.py
forbidden_paths:
  - docs/spec/**
---

# TASK-001 Fix fractional token refill accumulation and consume debit

## Outcome
`TokenBucketLimiter.refill` accrues tokens as a float so fractional balances persist across calls, and `consume` debits integer or fractional token counts correctly. Verified by a passing test asserting 1.5 tokens restored after 3s with `capacity=10, refill_rate=0.5`.

## References
- Change: CHG-001-fractional-token-refill
- Slice: SLICE-01
- `docs/spec/security/ratelimit.md#REQ-RL-01` (proportional refill preserving fractional balances)
- `docs/spec/security/ratelimit.md#REQ-RL-02` (consume debit returns True/False)

## Steps
1. Inspect `src/ratelimit/limiter.py` `refill`/`consume`.
2. Replace `int(elapsed * refill_rate)` with float accumulation of accrued tokens.
3. Ensure `consume` debits fractional counts and returns True/False per REQ-RL-02.
4. Add a test asserting 1.5 tokens restored after 3s (capacity=10, refill_rate=0.5).

## Test oracle
`TokenBucketLimiter(capacity=10, refill_rate=0.5)` after 3s restores 1.5 tokens; `consume` returns True and deducts when tokens remain, False without deduction.

## Unchanged behavior
`docs/spec/security/ratelimit.md` must NOT change (CR-005). Unknown-key and is_blocked behavior unchanged.

## Verification
```
python -m pytest tests/test_limiter.py
```
