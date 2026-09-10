# Request: Cooldown penalty for TokenBucketLimiter

## Summary

Extend the Rate Limiter capability (`security.ratelimit`) with an optional
coldown penalty. When a `TokenBucketLimiter` is initialized with
`penalty_seconds > 0`, a failed `consume` (insufficient tokens) puts the key
into a blocked state for `penalty_seconds`. While blocked, any `consume`
call for that key MUST return `False` immediately, even if tokens have
accumulated. After `penalty_seconds` elapses, the block is lifted on the
next request and normal consumption resumes. A new `is_blocked(key)` method
MUST return `True` while the key is under penalty and `False` otherwise.
Backward compatibility MUST be preserved: existing initializations without
`penalty_seconds` MUST behave exactly as before.

## Claims

### CR-001 (expectation)
Adding an optional `penalty_seconds` parameter (default `0.0`) to
`TokenBucketLimiter` initialization must be supported.

### CR-002 (expectation)
When `penalty_seconds > 0`, a failed `consume` (not enough tokens) must
transition the key into a blocked state lasting `penalty_seconds`.

### CR-003 (constraint)
While a key is blocked, any `consume` call for that key within the penalty
period MUST return `False` immediately, even if tokens accumulated during
that window.

### CR-004 (expectation)
After `penalty_seconds` elapses, the block must be lifted automatically on
the next request, resuming normal token-deduction logic.

### CR-005 (constraint)
The `is_blocked(key)` method MUST return `True` when the key is currently
under penalty and `False` otherwise.

### CR-006 (constraint)
Backward compatibility MUST be preserved: existing code initialized without
`penalty_seconds` MUST continue to work under the previous rules.

### CR-007 (hypothesis)
Unknowns: exact semantics of how penalty interacts with partial token
accumulation after the block lifts, and whether `is_blocked` should be
observable/testable independently of `consume`. These are not specified here
and are left for later analysis.
