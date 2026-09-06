# Change Request: Fractional Token Refill in TokenBucketLimiter

## Summary

`TokenBucketLimiter` currently computes refill using integer division
`int(elapsed * refill_rate)`, which drops fractional token accrual between
calls. For example, `TokenBucketLimiter(capacity=10, refill_rate=0.5)` after 3
seconds restores 1 token instead of the expected 1.5. The fix is to accrue
tokens as floats so fractional parts persist across successive calls, and to
make `consume` correctly deduct integer or fractional token amounts.

## Claims

### CR-001 (observation)
When initialized with `capacity=10, refill_rate=0.5`, after waiting 3 seconds
the limiter restores 1 token instead of the expected 1.5 tokens.

### CR-002 (observation)
The current refill formula uses integer division `int(elapsed * refill_rate)`,
which discards fractional token accrual between calls.

### CR-003 (expectation)
Tokens must accrue using floating-point arithmetic (`float`) so fractional
parts are not lost between successive calls.

### CR-004 (expectation)
The `consume` method must correctly deduct integer or fractional token amounts.

### CR-005 (constraint)
The specification `docs/spec/security/ratelimit.md` already requires
proportional refill ("tokens MUST be refilled proportionally to elapsed time")
and must NOT be changed (`spec unchanged`).

### CR-006 (hypothesis)
At the Target phase, a failing (Red) test reproducing fractional token
accrual at small time intervals should be created.

## Unknowns

- Exact language/runtime and test framework for `TokenBucketLimiter` not
  specified in the source.
- Whether existing callers depend on prior integer-refill behavior.
