# Request: Extend Rate Limiter with usage stats and rate policy

Source: docs/intake/S05.md

## Summary

The Rate Limiter product must be extended with two simultaneous changes:

1. A new capability `monitoring.usage_stats` that collects usage statistics per key (total consume calls, successful and rejected counts, peak load as max calls per second) and exposes them via a `get_stats(key)` method returning a dict.
2. A policy `security.rate_policy` that automatically blocks a key for a configurable period (default 300s) when a rejection threshold is exceeded (e.g. 50 rejected consumes in a row). A blocked key returns `False` from `consume` without consuming tokens and carries a `blocked_until` label in stats.

Both changes must be mutually compatible: stats must correctly reflect rejections caused by both token shortage and policy-based blocking. Integration tests verifying the interaction of both changes are required.

## Claims

- CR-001 (expectation): A new capability `monitoring.usage_stats` should be added to the Rate Limiter product.
- CR-002 (expectation): For each key, track total number of consume calls, number of successful and rejected requests, and peak load (maximum number of calls per second).
- CR-003 (expectation): A method `get_stats(key)` should return a dictionary with these values.
- CR-004 (expectation): A policy `security.rate_policy` should be added that, upon exceeding a rejection threshold (e.g. 50 rejected consumes in a row), automatically blocks the key for a configurable period (default 300 seconds).
- CR-005 (expectation): A blocked key should return `False` from `consume` without spending tokens and should carry a `blocked_until` label in stats.
- CR-006 (constraint): Both changes must be compatible with each other; stats must correctly reflect rejections caused by both token shortage and policy-based blocking.
- CR-007 (constraint): Integration tests verifying the interaction of both changes are required.
- CR-008 (observation): The source is a user request note; product specification and code were not read during intake.
