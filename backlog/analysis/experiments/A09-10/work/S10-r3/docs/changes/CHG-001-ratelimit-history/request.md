# Request: Rate Limiter consume attempt history

## Summary

The `security.ratelimit` service needs an attempt history for token consumption.
Each call to `consume(key, tokens)` must record an event (key, timestamp,
requested token count, and outcome `accepted`/`rejected`). A `get_history(key,
n=10)` method must return the last `n` events for a key, newest first. The
history must not change the semantics of `consume` (same keys, limits, and
results as without history). `n` must be an integer `>= 1` (exception
otherwise); default `n=10`; records for different keys must not mix.

## Claims

- CR-001 [observation]: The service `security.ratelimit` exposes a
  `consume(key, tokens)` method.
- CR-002 [expectation]: Every call to `consume(key, tokens)` records an event
  containing the key, the moment in time, the requested token count, and the
  outcome (`accepted` or `rejected`).
- CR-003 [expectation]: `get_history(key, n=10)` returns the last `n` events
  for the key, newest first.
- CR-004 [constraint]: The parameter `n` must be an integer `>= 1`; an
  exception is raised for invalid `n`.
- CR-005 [constraint]: Default value of `n` is 10.
- CR-006 [constraint]: Records for different keys must not be mixed.
- CR-007 [constraint]: History must not change the semantics of `consume`: the
  same keys, the same limits, and the same result as without history.
- CR-008 [hypothesis]: The history is stored per key; the storage backend and
  retention limits are not specified.
