# Change: CHG-001-ratelimit-consume-history

## Summary

The Rate Limiter service (`security.ratelimit`) needs a history of token-spend attempts. Each `consume(key, tokens)` call must record an event (key, timestamp, requested token count, outcome `accepted`/`rejected`), and `get_history(key, n=10)` must return the last `n` events for a key, newest first. History must not alter the semantics of `consume`.

## Claims

### CR-001 — observation
The service `security.ratelimit` currently exposes `consume(key, tokens)` but has no recorded history of attempts.

### CR-002 — expectation
Every call to `consume(key, tokens)` MUST record an event containing: the key, the moment in time, the requested number of tokens, and the outcome (`accepted` or `rejected`).

### CR-003 — expectation
The method `get_history(key, n=10)` MUST return the last `n` events for the given key, newest first.

### CR-004 — constraint
The parameter `n` MUST be an integer `>= 1`. An invalid `n` MUST raise an exception.

### CR-005 — constraint
History recording MUST NOT change the semantics of `consume`: same keys, same limits, same result as without history.

### CR-006 — expectation
Default value of `n` is `10`. Records for different keys MUST NOT be mixed.

## Unknowns

- Storage backend for history (in-memory, disk, external store) is not specified.
- Retention / eviction policy beyond the `n` returned by `get_history` is not specified.
- Concurrency and durability requirements are not specified.
