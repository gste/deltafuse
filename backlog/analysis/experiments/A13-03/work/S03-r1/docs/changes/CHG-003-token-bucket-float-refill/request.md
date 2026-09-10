# Change Request: CHG-003-token-bucket-float-refill

## Summary
`TokenBucketLimiter` loses fractional token accrual because refill uses integer division `int(elapsed * refill_rate)`. With `capacity=10, refill_rate=0.5`, after 3s only 1 token is restored instead of 1.5. Refill must accumulate as float so fractional parts persist across calls; `consume` must debit integer or fractional token counts. The existing spec `docs/spec/security/ratelimit.md` already requires proportional refill and must NOT change.

## Claims

- CR-001 (observation): After `TokenBucketLimiter(capacity=10, refill_rate=0.5)` and a 3s wait, 1 token is restored instead of the expected 1.5, because refill uses `int(elapsed * refill_rate)`.
- CR-002 (expectation): Refill must accumulate tokens as `float` so fractional parts are not lost between successive calls.
- CR-003 (expectation): `consume` must correctly debit an integer or fractional number of tokens.
- CR-004 (constraint): `docs/spec/security/ratelimit.md` already requires proportional refill and must remain unchanged (`spec unchanged`).
- CR-005 (hypothesis): At Target, a failing (Red) test reproducing fractional-token accrual at small time intervals should be created.
