# Request: Burst-window statistics for Rate Limiter (S11-B)

## Summary

In the Rate Limiter service (`security.ratelimit`), add a way to sample statistics
for a key over the current burst window. A new method `get_window_stats(key)` must
return a dictionary with fields `accepted`, `rejected`, and `remaining_tokens` for
the key. Window counters reset together with the existing token replenishment logic.
Calling statistics must not consume tokens or change limits. For an unknown key,
return zero counters and the current remainder per the key-initialization rules.

## Claims

### CR-001 — observation
The service `security.ratelimit` currently exposes token replenishment logic that
resets window counters, but no public method to read per-key window statistics.

### CR-002 — expectation
`get_window_stats(key)` must return a dict with exactly the fields `accepted`,
`rejected`, and `remaining_tokens` for the requested key.

### CR-003 — expectation
Window counters used by `get_window_stats` are reset together with the existing
token replenishment logic (no separate reset path).

### CR-004 — constraint
Calling `get_window_stats` must not consume tokens and must not change any limits.

### CR-005 — expectation
For an unknown key, `get_window_stats` returns zero counters (`accepted=0`,
`rejected=0`) and the current `remaining_tokens` following the key-initialization
rules.

### CR-006 — hypothesis
The remainder for an unknown key is derived from the same key-initialization rules
used when a key is first seen; the exact formula is not specified in the source and
should be confirmed against the existing implementation.

### CR-007 — unknown
The exact return type contract (e.g. plain dict vs. frozen/typed mapping) and
whether `remaining_tokens` for an unknown key reflects a freshly initialized key
state are not fully specified and need confirmation.
