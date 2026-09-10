# Request: Add optional cooldown penalty to TokenBucketLimiter

## Summary

The Rate Limiter service (`security.ratelimit`) needs an optional cooldown
penalty. When `consume` fails due to insufficient tokens, the key may enter a
blocked state for a configurable duration. While blocked, further `consume`
calls must return `False` immediately even if tokens have accumulated. The
block auto-clears after the penalty period on the next request, restoring normal
spending logic. A new `is_blocked(key)` method reports the blocked state.

## Claims

### CR-001 (expectation)
`TokenBucketLimiter` initialization accepts an optional parameter `penalty_seconds`
with a default value of `0.0`.

### CR-002 (expectation)
When `penalty_seconds > 0`, a failed `consume` attempt (insufficient tokens)
transitions the key into a blocked state lasting `penalty_seconds`.

### CR-003 (constraint)
While a key is blocked within the penalty window, any `consume` call for that
key MUST return `False` immediately, even if tokens have accumulated during the
block.

### CR-004 (expectation)
After `penalty_seconds` elapses, the block is automatically lifted on the next
request and normal token-spending logic resumes.

### CR-005 (constraint)
The method `is_blocked(key)` MUST return `True` when the key is currently under
penalty and `False` otherwise.

### CR-006 (constraint)
Backward compatibility must be preserved: existing code that does not pass
`penalty_seconds` must continue to behave under the previous rules.

### CR-007 (hypothesis)
Unknowns: exact semantics of the penalty window boundary (inclusive vs exclusive),
whether the block timer starts at the failed `consume` call, and how the block
interacts with concurrent or interleaved `consume` calls. These require
clarification during analysis.
