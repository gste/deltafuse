# Change Request: Fractional Token Refill in TokenBucketLimiter

## Summary
`TokenBucketLimiter` uses integer division `int(elapsed * refill_rate)` when refilling, which drops fractional token accrual between calls. With `capacity=10, refill_rate=0.5`, after 3 seconds only 1 token is restored instead of 1.5. Refill must accumulate as float so fractional parts persist across successive calls; `consume` must debit integer or fractional token counts correctly. The existing spec `docs/spec/security/ratelimit.md` already requires proportional refill and must remain unchanged.

## Claims

- CR-001 [observation]: With `TokenBucketLimiter(capacity=10, refill_rate=0.5)`, after waiting 3 seconds only 1 token is restored instead of the expected 1.5 tokens.
- CR-002 [hypothesis]: The defect is caused by integer division `int(elapsed * refill_rate)` in the refill formula, which discards fractional token accrual between calls.
- CR-003 [expectation]: Refill must accumulate tokens as float so fractional parts are not lost between successive calls.
- CR-004 [expectation]: The `consume` method must correctly debit an integer or fractional number of tokens.
- CR-005 [constraint]: `docs/spec/security/ratelimit.md` already requires proportional refill and must NOT be changed (spec unchanged).
- CR-006 [expectation]: At the Target phase, a failing (Red) test reproducing fractional token accrual at small time intervals must be created.

## Unknowns
- Exact current refill/consume implementation details not inspected (product code unread during intake).
- Whether fractional tokens are exposed to callers or only tracked internally.
