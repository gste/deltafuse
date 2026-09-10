# Request: Add optional cooldown penalty to TokenBucketLimiter

## Summary

Extend the Rate Limiter capability (`security.ratelimit`) with an optional
cool-down penalty. When `TokenBucketLimiter` is initialized with a positive
`penalty_seconds`, a failed `consume` (insufficient tokens) puts the key into a
blocked state for `penalty_seconds`. While blocked, further `consume` calls for
that key must return `False` immediately even if tokens have accumulated. After
the penalty elapses, the block is lifted automatically on the next request and
normal consumption resumes. A new `is_blocked(key)` method reports whether a key
is currently penalized. Backward compatibility must be preserved: existing
initialization without `penalty_seconds` must behave exactly as before.

## Claims

### CR-001 (expectation)
Adding an optional `penalty_seconds` parameter to `TokenBucketLimiter`
initialization, defaulting to `0.0`.

### CR-002 (expectation)
When `penalty_seconds > 0`, a failed `consume` (tokens insufficient) transitions
the key into a blocked state for `penalty_seconds`.

### CR-003 (constraint)
While a key is blocked, any `consume` call for that key within the penalty
window MUST return `False` immediately, even if tokens have accumulated during
that period.

### CR-004 (expectation)
After `penalty_seconds` elapses, the block is lifted automatically on the next
request and normal consumption logic resumes.

### CR-005 (constraint)
The `is_blocked(key)` method MUST return `True` when the key is currently under
penalty and `False` otherwise.

### CR-006 (constraint)
Backward compatibility: existing code that initializes `TokenBucketLimiter`
without `penalty_seconds` MUST continue to work under the previous rules.

### CR-007 (hypothesis)
Unknowns: exact language/platform of the Rate Limiter service, the internal
storage representation of blocked keys, and how existing tests exercise the
limiter. These require reading the product code during analysis.
