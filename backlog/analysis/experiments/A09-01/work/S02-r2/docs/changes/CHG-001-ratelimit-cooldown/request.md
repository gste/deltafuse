# Request: Add optional cooldown penalty to TokenBucketLimiter

Source: `docs/intake/S02.md`

## Summary

Extend the Rate Limiter capability (`security.ratelimit`) with an optional
time-based lock ("cool-down penalty") that activates when a `consume` call
fails due to insufficient tokens.

## Claims

### Observation

- O1: The service `Rate Limiter` (`security.ratelimit`) currently exposes a
  `TokenBucketLimiter` whose `consume` returns `False` when tokens are
  insufficient. [source: docs/intake/S02.md]
- O2: `TokenBucketLimiter` is initialized without any penalty/cooldown
  parameter today. [source: docs/intake/S02.md]

### Expectation

- E1: `TokenBucketLimiter` MUST accept an optional `penalty_seconds` parameter
  defaulting to `0.0`. [source: docs/intake/S02.md]
- E2: When `penalty_seconds > 0`, a failed `consume` (insufficient tokens)
  MUST transition the key into a locked state for `penalty_seconds`. [source:
  docs/intake/S02.md]
- E3: While a key is locked, any `consume` call within the penalty window MUST
  return `False` immediately, even if tokens have accumulated. [source:
  docs/intake/S02.md]
- E4: After `penalty_seconds` elapses, the lock MUST be released automatically
  on the next request and normal consumption logic MUST resume. [source:
  docs/intake/S02.md]
- E5: A method `is_blocked(key)` MUST return `True` when the key is currently
  under penalty and `False` otherwise. [source: docs/intake/S02.md]

### Constraint

- C1: Backward compatibility MUST be preserved: existing callers that do not
  pass `penalty_seconds` MUST behave exactly as before. [source:
  docs/intake/S02.md]

### Hypothesis

- H1: The cooldown state can be modeled as a per-key lock timestamp that is
  lazily evaluated on the next `consume`/`is_blocked` call. [inferred]

### Unknowns

- U1: Exact language/runtime and public API surface of `TokenBucketLimiter`
  are not yet confirmed (product code not read during intake).
- U2: Whether `is_blocked` is a new public API or an internal helper is not
  specified.
- U3: Interaction between cooldown lock and concurrent token accrual is not
  fully specified.
