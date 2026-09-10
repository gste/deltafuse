# Change Request: Fractional Token Refill in TokenBucketLimiter

## Summary

`TokenBucketLimiter` loses fractional token accrual between calls because refill
uses integer division `int(elapsed * refill_rate)`. With `capacity=10,
refill_rate=0.5`, after 3 seconds only 1 token is restored instead of 1.5.

## Claims

### CR-001 (observation)
When initialized with `TokenBucketLimiter(capacity=10, refill_rate=0.5)`, after
waiting 3 seconds only 1 token is restored instead of the expected 1.5 tokens.

### CR-002 (observation)
The refill formula uses integer division `int(elapsed * refill_rate)` rather than
a float computation that preserves the fractional remainder across calls.

### CR-003 (expectation)
Refill must accumulate tokens as a float so fractional parts are not lost between
sequential calls.

### CR-004 (expectation)
The `consume` method must correctly deduct integer or fractional token counts.

### CR-005 (constraint)
`docs/spec/security/ratelimit.md` already requires proportional refill
("tokens MUST be refilled proportionally to elapsed time"); the specification is
correct and must NOT change (`spec unchanged`).

### CR-006 (hypothesis)
At the Target phase, a failing (Red) test reproducing fractional-token accrual at
small time intervals should be created.

## Unknowns

- Exact language / file containing `TokenBucketLimiter` not yet located (intake
  does not read product code).
- Whether existing tests assert integer behavior that would need updating.
