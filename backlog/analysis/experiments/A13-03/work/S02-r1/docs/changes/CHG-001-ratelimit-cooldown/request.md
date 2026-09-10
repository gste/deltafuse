# Request: Add optional cooldown penalty to TokenBucketLimiter

## Summary

Extend the Rate Limiter service (`security.ratelimit`) with an optional
cool-down penalty. When a `consume` attempt fails due to insufficient tokens
and `penalty_seconds > 0`, the key enters a blocked state for `penalty_seconds`.
Blocked keys immediately return `False` on any `consume` during the penalty
window, even if tokens have accumulated. The block lifts automatically on the
next request after the window elapses, restoring normal consumption logic.

## Claims

### CR-001 (expectation)
Add an optional parameter `penalty_seconds` (default `0.0`) to the
`TokenBucketLimiter` initializer.

### CR-002 (expectation)
When `penalty_seconds > 0`, a failed `consume` (insufficient tokens) moves the
key into a blocked state for `penalty_seconds`.

### CR-003 (expectation)
Any `consume` call for a blocked key within the penalty window MUST return
`False` immediately, even if tokens accumulated during that window.

### CR-004 (expectation)
After `penalty_seconds` elapses, the block lifts automatically on the next
request and normal consumption logic resumes.

### CR-005 (expectation)
`is_blocked(key)` MUST return `True` when the key is currently under penalty
and `False` otherwise.

### CR-006 (constraint)
Backward compatibility must be preserved: existing code that initializes the
limiter without `penalty_seconds` must continue to behave under the previous
rules.

## Unknowns

- Exact language/framework of `security.ratelimit` is not yet read; the
  implementation route is assumed to be code pending analysis.
- The precise semantics of "next request" for block removal (first call after
  window vs. lazy check) are not yet pinned.
