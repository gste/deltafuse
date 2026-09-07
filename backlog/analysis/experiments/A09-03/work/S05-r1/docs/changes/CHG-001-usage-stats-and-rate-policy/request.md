# Request: Extend Rate Limiter with Usage Stats and Rate Policy Auto-Block

Source: `docs/intake/S05.md` (user request in Russian, translated here).

## Summary

The user requests two simultaneous changes to the Rate Limiter product:

1. A new capability `monitoring.usage_stats` that collects usage statistics per key: total `consume` calls, count of successful and rejected requests, and peak load (max calls per second). A `get_stats(key)` method must return a dict with these values.
2. A policy `security.rate_policy` that, when the rejection threshold is exceeded (e.g. 50 rejected `consume` calls in a row), automatically blocks the key for a configurable period (default 300 seconds). A blocked key must return `False` from `consume` without consuming tokens and expose a `blocked_until` label in stats.

Both changes must be compatible: stats must correctly reflect rejections caused by both token shortage and policy-based blocking. Integration tests verifying the interaction of both changes are required.

## Claims

### CR-001 (observation)
The product contains a Rate Limiter whose `consume` method currently returns a boolean and consumes tokens on each call. [source: docs/intake/S05.md]

### CR-002 (expectation)
A new capability `monitoring.usage_stats` must be added that tracks, per key: total number of `consume` calls, number of successful calls, number of rejected calls, and peak load (maximum number of calls in one second). [source: docs/intake/S05.md]

### CR-003 (expectation)
A method `get_stats(key)` must be added that returns a dictionary containing the tracked values from CR-002. [source: docs/intake/S05.md]

### CR-004 (expectation)
A policy `security.rate_policy` must be added that automatically blocks a key when the number of consecutive rejected `consume` calls exceeds a threshold (example value given: 50). [source: docs/intake/S05.md]

### CR-005 (expectation)
The block duration must be configurable, defaulting to 300 seconds. [source: docs/intake/S05.md]

### CR-006 (expectation)
A blocked key must return `False` from `consume` without consuming tokens, and its stats must include a `blocked_until` field. [source: docs/intake/S05.md]

### CR-007 (expectation)
Stats must correctly reflect rejections caused by both token shortage and policy-based blocking. [source: docs/intake/S05.md]

### CR-008 (constraint)
Both changes must be mutually compatible. [source: docs/intake/S05.md]

### CR-009 (expectation)
Integration tests must verify the interaction between the usage stats capability and the rate policy auto-block. [source: docs/intake/S05.md]

### CR-010 (hypothesis)
The example threshold value (50) and default block duration (300s) are illustrative; exact values may need to be confirmed as configurable parameters rather than hard requirements. [source: docs/intake/S05.md]

### CR-011 (constraint)
No acceptance criteria, technical design, capability routing, or spec references are asserted here; these are left for later phases. [this document]
