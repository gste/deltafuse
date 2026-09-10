# Request: Window statistics for rate limiter key (S11-B)

## Summary

In the Rate Limiter service (`security.ratelimit`), add a way to sample
statistics for a key over the current window. The new method must return
per-key counters without consuming tokens or changing limits.

## Claims

- CR-001 [expectation]: Method `get_window_stats(key)` must return a dict with
  fields `accepted`, `rejected`, `remaining_tokens` for the key.
- CR-002 [constraint]: Window counters reset together with the token-refill
  logic of the existing limiter.
- CR-003 [constraint]: Calling statistics must not spend tokens or change limits.
- CR-004 [expectation]: For an unknown key, return zero counters and the
  current remainder per the key-initialization rules.

## Unknowns

- Exact key-initialization rules that define the remainder for an unknown key
  are not specified here; confirm against the existing limiter implementation.
- Whether `accepted`/`rejected` are cumulative or window-scoped is not stated.
