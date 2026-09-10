# Request: Add optional cooldown penalty to TokenBucketLimiter

## Summary

In the Rate Limiter service (`security.ratelimit`), add an optional cooldown
penalty to `TokenBucketLimiter`. When enabled, a failed `consume` (not enough
tokens) puts the key into a blocked state for `penalty_seconds`. While blocked,
any `consume` for that key must return `False` immediately even if tokens have
accumulated. After `penalty_seconds` elapses, the block is lifted automatically
on the next request and normal consumption resumes. A new `is_blocked(key)`
method must report whether a key is currently penalized. Backward compatibility
must be preserved: existing callers without `penalty_seconds` keep the previous
behavior.

## Claims

### CR-001 — observation
The `TokenBucketLimiter` currently lives in the `security.ratelimit`
service. (Not yet verified against product code.)

### CR-002 — expectation
`TokenBucketLimiter` initialization accepts an optional `penalty_seconds`
parameter defaulting to `0.0`.

### CR-003 — expectation
When `penalty_seconds > 0`, a failed `consume` (insufficient tokens) places
the key into a blocked state lasting `penalty_seconds`.

### CR-004 — expectation
While a key is blocked, every `consume` call for that key returns `False`
immediately, even if tokens have accumulated during the penalty window.

### CR-005 — expectation
After `penalty_seconds` elapses, the block is lifted automatically on the
next request and normal token-consumption logic resumes.

### CR-006 — expectation
`is_blocked(key)` returns `True` when the key is currently under penalty and
`False` otherwise.

### CR-007 — constraint
Backward compatibility must be preserved: existing code that does not pass
`penalty_seconds` must continue to behave under the previous rules.

### CR-008 — hypothesis
The exact semantics of "blocked" vs "normal insufficient tokens" and the
interaction with token accrual during the penalty window need confirmation
against the existing implementation.

### CR-009 — unknown
The concrete language, storage of per-key state, and clock source used by the
service are not yet known (product code not read).
