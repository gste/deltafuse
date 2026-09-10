# Request: Rate Limiter consume() attempt history

## Summary

The `security.ratelimit` service needs an attempt history for token consumption.
Each `consume(key, tokens)` call must record an event (key, timestamp,
requested token count, and outcome `accepted`/`rejected`). A `get_history(key,
n=10)` method must return the last `n` events for a key, newest first. The
history must not change the semantics of `consume` (same keys, limits, and
results as without history).

## Claims

### CR-001 — observation
The service `security.ratelimit` currently exposes `consume(key, tokens)`.

### CR-002 — expectation
Every `consume(key, tokens)` call must record an event containing the key, the
timestamp, the requested token count, and the outcome (`accepted` or
`rejected`).

### CR-003 — expectation
`get_history(key, n=10)` must return the last `n` events for `key`, newest
first.

### CR-004 — constraint
The parameter `n` must be an integer `>= 1`; an invalid `n` must raise an
exception.

### CR-005 — constraint
Default value of `n` is `10`.

### CR-006 — constraint
Records for different keys must not be mixed.

### CR-007 — constraint
History must not change the semantics of `consume`: same keys, same limits,
same result as without history tracking.

### CR-008 — hypothesis
The storage mechanism for history is not specified (implementation detail to be
determined during analysis).
