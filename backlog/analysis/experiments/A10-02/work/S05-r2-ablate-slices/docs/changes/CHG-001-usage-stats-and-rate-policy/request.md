# Request: Extend Rate Limiter with Usage Stats and Rate Policy Auto-Block

Source: `docs/intake/S05.md` (user request in Russian).

## Summary

The user requests two simultaneous changes to the Rate Limiter product:

1. A new capability `monitoring.usage_stats` that collects per-key usage statistics
   (total `consume` calls, successful and declined counts, peak load as max calls per
   second) and exposes them via a `get_stats(key)` method returning a dict.
2. A policy `security.rate_policy` that automatically blocks a key for a configurable
   period (default 300s) once a decline threshold is exceeded (e.g. 50 consecutive
   declined `consume` calls). A blocked key must return `False` from `consume` without
   consuming tokens and expose a `blocked_until` field in stats.

Both changes must be mutually compatible: stats must correctly reflect declines caused
by both token exhaustion and policy-based blocking. Integration tests covering the
interaction of both changes are required.

## Claims

- CR-001 [observation] The product under change is a Rate Limiter; the user references
  a `consume` method that returns a boolean and consumes tokens.
- CR-002 [expectation] A new capability `monitoring.usage_stats` must be added that
  tracks, per key: total `consume` count, number of successful consumes, number of
  declined consumes, and peak load (max number of calls in one second).
- CR-003 [expectation] A `get_stats(key)` method must return a dict containing the
  values described in CR-002.
- CR-004 [expectation] A policy `security.rate_policy` must block a key for a
  configurable period (default 300 seconds) when the decline threshold is exceeded
  (example threshold: 50 consecutive declined `consume` calls).
- CR-005 [expectation] A blocked key must return `False` from `consume` without
  consuming tokens and must expose a `blocked_until` field in its stats.
- CR-006 [constraint] Stats must correctly reflect declines caused by both token
  exhaustion and policy-based blocking; the two changes must be compatible.
- CR-007 [expectation] Integration tests must verify the interaction between the
  usage-stats capability and the rate-policy auto-block.
- CR-008 [hypothesis] The example values (50 consecutive declines, 300s default block
  period) are illustrative; exact threshold and default durations are not yet fixed.
- CR-009 [unknown] The concrete implementation language, data structures, and API
  surface of the Rate Limiter are not specified in the source and were not read from
  product code.
- CR-010 [unknown] Whether `get_stats(key)` should exist already or must be created
  anew is not stated.
