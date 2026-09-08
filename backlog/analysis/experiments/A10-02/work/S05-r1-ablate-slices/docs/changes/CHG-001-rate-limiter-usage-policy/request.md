# Request: Extend Rate Limiter with Usage Stats and Rate Policy

Source: `docs/intake/S05.md` (user request in Russian, translated here).

## Summary

Two simultaneous changes are requested for the Rate Limiter product:

1. A new capability `monitoring.usage_stats` that collects usage statistics per key: total `consume` calls, counts of successful and rejected requests, and peak load (max calls per second). A `get_stats(key)` method must return a dict with these values.
2. A policy `security.rate_policy` that, when a rejection threshold is exceeded (e.g. 50 rejected `consume` calls in a row), automatically blocks the key for a configurable period (default 300 seconds). A blocked key must return `False` from `consume` without consuming tokens and expose a `blocked_until` label in stats.

Both changes must be compatible: stats must correctly reflect rejections caused by both token shortage and policy-based blocking. Integration tests verifying the interaction of both changes are required.

## Claims

- CR-001 (observation): The source request is a single document `docs/intake/S05.md` describing two related product changes.
- CR-002 (expectation): Add capability `monitoring.usage_stats` tracking per key: total consume calls, successful consume count, rejected consume count, and peak load (max calls per second).
- CR-003 (expectation): Provide a `get_stats(key)` method returning a dict containing the tracked values.
- CR-004 (expectation): Add policy `security.rate_policy` that blocks a key after a configurable rejection threshold (example: 50 rejected consume calls in a row) for a configurable period (example default 300 seconds).
- CR-005 (expectation): A blocked key returns `False` from `consume` without consuming tokens and exposes `blocked_until` in stats.
- CR-006 (constraint): Stats must correctly reflect rejections caused by both token shortage and policy-based blocking.
- CR-007 (expectation): Integration tests must verify the interaction between the usage_stats capability and the rate_policy.
- CR-008 (hypothesis): The rejection threshold default is 50 and the block period default is 300 seconds; these are illustrative examples in the source, not confirmed requirements.
- CR-009 (constraint): No acceptance criteria, technical design, or spec references are asserted here; these are deferred to later phases.
