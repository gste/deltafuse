# Request: Extend Rate Limiter with Usage Stats and Rate Policy Auto-Block

Source: `docs/intake/S05.md` (user request in Russian).

## Summary

The user requests two simultaneous changes to the product "Rate Limiter":

1. A new capability `monitoring.usage_stats` that collects usage statistics per key: total `consume` calls, count of successful and rejected requests, and peak load (max calls per second). A `get_stats(key)` method must return a dict with these values.
2. A policy `security.rate_policy` that, when the rejection threshold is exceeded (e.g. 50 rejected `consume` calls in a row), automatically blocks the key for a configurable period (default 300 seconds). A blocked key must return `False` from `consume` without consuming tokens and expose a `blocked_until` label in stats.

Both changes must be compatible with each other: stats must correctly reflect rejections caused by both token shortage and policy-based blocking. Integration tests verifying the interaction of both changes are required.

## Claims

### CR-001 (expectation)
A new capability `monitoring.usage_stats` should be added to the Rate Limiter product.

### CR-002 (expectation)
Per key, the capability must track: total number of `consume` calls, number of successful calls, number of rejected calls, and peak load (maximum number of calls per one second).

### CR-003 (expectation)
A method `get_stats(key)` must return a dictionary containing the tracked values from CR-002.

### CR-004 (expectation)
A policy `security.rate_policy` must be added that, upon exceeding a rejection threshold, automatically blocks the key for a configurable period.

### CR-005 (hypothesis)
The rejection threshold example is 50 rejected `consume` calls in a row; the exact threshold semantics (consecutive vs cumulative) are not fully specified.

### CR-006 (expectation)
The default blocking period is 300 seconds; the period must be configurable.

### CR-007 (expectation)
A blocked key must return `False` from `consume` without consuming tokens.

### CR-008 (expectation)
The stats of a blocked key must include a `blocked_until` label/marker.

### CR-009 (constraint)
Both changes must be mutually compatible: stats must correctly reflect rejections caused by both token shortage and policy-based blocking.

### CR-010 (expectation)
Integration tests verifying the interaction of both changes are required.

### CR-011 (unknown)
The concrete Rate Limiter implementation, its existing API, storage model, and where new capabilities/policies are registered are not read and remain unknown at this stage.

### CR-012 (unknown)
The exact semantics of "peak load (max calls per second)" (sliding window vs fixed bucket, resolution) are not specified.

### CR-013 (unknown)
The exact semantics of the rejection threshold (consecutive 50 vs cumulative 50) are not specified.
