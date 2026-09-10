# Change Request: Fractional Token Refill in TokenBucketLimiter

## Summary
`TokenBucketLimiter` loses fractional token accrual because refill uses integer division `int(elapsed * refill_rate)`. With `capacity=10, refill_rate=0.5` after 3s only 1 token is restored instead of 1.5. Refill must accumulate as float so fractional parts persist across calls; `consume` must debit integer or fractional counts correctly. The existing spec `docs/spec/security/ratelimit.md` already requires proportional refill and must NOT change.

## Claims

- CR-001 [observation] After `TokenBucketLimiter(capacity=10, refill_rate=0.5)` and 3s wait, 1 token is restored instead of 1.5.
- CR-002 [hypothesis] Refill uses integer division `int(elapsed * refill_rate)` instead of float, discarding fractional remainder between calls.
- CR-003 [expectation] Refill must accumulate tokens as float so fractional parts are not lost between successive calls.
- CR-004 [expectation] `consume` must correctly debit integer or fractional token counts.
- CR-005 [constraint] `docs/spec/security/ratelimit.md` already requires proportional refill; it must remain unchanged (spec unchanged).
- CR-006 [expectation] At Target stage, create a failing (Red) test reproducing fractional token accrual at small time intervals.
- CR-007 [unknown] Exact refill formula and float precision handling are not specified; to be resolved during analysis.
