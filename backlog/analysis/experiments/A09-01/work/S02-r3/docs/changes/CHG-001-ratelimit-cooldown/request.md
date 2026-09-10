# Request: Add optional cooldown penalty to TokenBucketLimiter

## Summary

In the Rate Limiter service (`security.ratelimit`), add an optional cooldown
penalty to `TokenBucketLimiter`. When enabled via a new `penalty_seconds`
parameter, a failed `consume` (insufficient tokens) places the key into a
blocked state for `penalty_seconds`. While blocked, any `consume` call for that
key must return `False` immediately even if tokens have accumulated. After the
penalty elapses, the block is lifted automatically on the next request and
normal consumption logic resumes. A new `is_blocked(key)` method reports whether
a key is currently under penalty. Backward compatibility must be preserved: code
initialized without `penalty_seconds` must behave exactly as before.

## Claims

### CR-001 — observation
The `TokenBucketLimiter` currently lives in the `security.ratelimit`
service. This is derived from the request text; the source code was not read.

### CR-002 — expectation
`TokenBucketLimiter.__init__` (or equivalent constructor) gains an optional
parameter `penalty_seconds` that defaults to `0.0`.

### CR-003 — expectation
When `penalty_seconds > 0`, a failed `consume` (not enough tokens) transitions
the key into a blocked state lasting `penalty_seconds`.

### CR-004 — expectation
While a key is blocked, every `consume` call for that key returns `False`
immediately, even if tokens have accumulated during the penalty window.

### CR-005 — expectation
After `penalty_seconds` elapses, the block is lifted automatically on the next
request and normal token-consumption logic resumes.

### CR-006 — expectation
A new method `is_blocked(key)` returns `True` when the key is currently under
penalty and `False` otherwise.

### CR-007 — constraint
Backward compatibility must be preserved: existing callers that do not pass
`penalty_seconds` must continue to work under the previous rules.

### CR-008 — hypothesis (unknown)
It is not yet known how the existing implementation tracks per-key state, token
accumulation, or timing. This must be confirmed against the actual code during
analysis.

### CR-009 — hypothesis (unknown)
It is not yet known the exact language, module path, and public API surface of
`security.ratelimit`. This must be confirmed during analysis.
