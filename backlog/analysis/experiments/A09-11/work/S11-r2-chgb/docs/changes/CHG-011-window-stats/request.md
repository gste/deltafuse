# Request: Burst-window statistics for Rate Limiter (S11-B)

## Summary

The Rate Limiter service (`security.ratelimit`) needs a way to sample window statistics for a key over the current burst window. A new method `get_window_stats(key)` should return accepted/rejected/remaining_tokens counts for the key without consuming tokens or changing limits. For an unknown key, it should return zero counters and the current remainder per the key-initialization rules.

## Claims

### CR-001 — observation
The Rate Limiter service is located at `security.ratelimit`.

### CR-002 — expectation
A method `get_window_stats(key)` must return a dictionary with the fields `accepted`, `rejected`, and `remaining_tokens` for the given key.

### CR-003 — expectation
Window counters are reset together with the token-replenishment logic of the existing limiter.

### CR-004 — constraint
Calling the statistics method must not consume tokens and must not change limits.

### CR-005 — expectation
For an unknown key, the method must return zero counters and the current remainder according to the key-initialization rules.

### CR-006 — hypothesis
The existing limiter already tracks per-key accepted/rejected counters and a current remainder that can be exposed without side effects.

### CR-007 — unknown
Exact semantics of the key-initialization rules for `remaining_tokens` on an unknown key are not specified here and must be resolved from the existing limiter implementation.
