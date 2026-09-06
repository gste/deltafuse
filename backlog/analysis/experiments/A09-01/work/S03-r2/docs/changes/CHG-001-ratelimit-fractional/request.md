# Change Request: Fractional Token Refill in TokenBucketLimiter

## Summary

The `TokenBucketLimiter` loses fractional token accrual because refill uses integer
division `int(elapsed * refill_rate)` instead of float accumulation. Given
`capacity=10, refill_rate=0.5`, after 3 seconds only 1 token is restored instead of
1.5. The fix must accumulate tokens as floats so fractional parts persist across
calls, and `consume` must correctly debit integer or fractional token counts.

## Claims

### CR-001 (observation)
When `TokenBucketLimiter(capacity=10, refill_rate=0.5)` waits 3 seconds, it
restores 1 token instead of the expected 1.5, because refill uses integer
division `int(elapsed * refill_rate)`.

### CR-002 (expectation)
Refill must accumulate tokens as floats so fractional parts are not lost between
sequential calls.

### CR-003 (expectation)
The `consume` method must correctly debit an integer or fractional number of
tokens.

### CR-004 (constraint)
`docs/spec/security/ratelimit.md` already requires proportional refill
("tokens MUST be refilled proportionally to elapsed time"); the specification is
correct and MUST NOT change (`spec unchanged`).

### CR-005 (hypothesis)
A Red test at Target reproducing fractional-token accrual at small time
intervals should fail against the current integer-division implementation.

### CR-006 (unknown)
Exact float accumulation policy (e.g., whether to cap fractional carry at
capacity, rounding behavior) is not yet specified.
