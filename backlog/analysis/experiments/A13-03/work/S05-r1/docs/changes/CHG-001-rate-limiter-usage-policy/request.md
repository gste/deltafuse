# Request: Extend Rate Limiter with usage stats and rate policy

Source: docs/intake/S05.md

## Summary

The Rate Limiter product must be extended in two simultaneous, mutually
compatible ways: (1) a new capability `monitoring.usage_stats` that collects
per-key usage statistics via a new `get_stats(key)` method, and (2) a new
policy `security.rate_policy` that automatically blocks a key after a threshold
of consecutive denied consumes. Both changes must be compatible with each other,
and integration tests must verify their interaction.

## Claims

- CR-001 (expectation): A new capability `monitoring.usage_stats` should be added
  that tracks, per key, the total number of `consume` calls, the number of
  successful and denied requests, and peak load (maximum number of calls per
  second).

- CR-002 (expectation): A method `get_stats(key)` must return a dictionary
  containing these values (total consumes, successful, denied, peak load per
  second).

- CR-003 (expectation): A new policy `security.rate_policy` should block a key
  automatically when the number of consecutive denied `consume` calls exceeds a
  threshold (example given: 50 consecutive denials), for a configurable period
  (default 300 seconds).

- CR-004 (expectation): A blocked key must return `False` from `consume` without
  consuming tokens, and its stats must include a `blocked_until` label.

- CR-005 (constraint): Both changes must be compatible with each other; stats
  must correctly reflect denials caused by both token shortage and policy-based
  blocking.

- CR-006 (expectation): Integration tests are required that verify the
  interaction between the usage-stats capability and the rate-policy blocking.

- CR-007 (constraint): Threshold and block duration are configurable; the
  default block duration is 300 seconds. Threshold example value is 50
  consecutive denials (exact value to be confirmed).

- CR-008 (hypothesis): Peak load should be measured as the maximum number of
  `consume` calls observed within any single one-second window.

- CR-009 (unknown): The exact data types and key names inside the `get_stats`
  return dictionary are not specified and must be defined.

- CR-010 (unknown): Whether `blocked_until` is an absolute timestamp or a
  relative duration is not specified and must be defined.
