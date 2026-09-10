# Request: Extend Rate Limiter with usage stats and rate policy auto-block

Source: docs/intake/S05.md (user request, Russian)

## Summary

The user requests two simultaneous, mutually compatible changes to the Rate Limiter product:

1. A new capability `monitoring.usage_stats` that collects per-key usage statistics (total `consume` calls, successful and denied counts, and peak load = max calls per second) and exposes them via a `get_stats(key)` method returning a dict.
2. A new policy `security.rate_policy` that, when a configurable threshold of consecutive denied consumes is exceeded (e.g. 50), automatically blocks the key for a configurable period (default 300s). A blocked key returns `False` from `consume` without consuming tokens and carries a `blocked_until` marker in stats.

Both changes must be compatible: stats must correctly reflect denials caused by both token shortage and policy-based blocking. Integration tests covering the interaction of both changes are required.

## Claims

### CR-001 — observation
The source is a raw user request (docs/intake/S05.md) describing desired behavior for an existing Rate Limiter product. No product spec or code was read during intake.

### CR-002 — expectation
A new capability `monitoring.usage_stats` shall be added. For each key it shall track: total number of `consume` calls, number of successful consumes, number of denied consumes, and peak load (maximum number of calls in a single second). A method `get_stats(key)` shall return a dict containing these values.

### CR-003 — expectation
A new policy `security.rate_policy` shall be added. When the number of consecutive denied `consume` calls for a key reaches a configurable threshold (example value 50), the key shall be automatically blocked for a configurable period (default 300 seconds). While blocked, `consume` shall return `False` without consuming tokens, and stats for the key shall include a `blocked_until` marker.

### CR-004 — constraint
The two changes must be mutually compatible. `get_stats` must correctly count denials caused by both token shortage and policy-based blocking.

### CR-005 — constraint
Integration tests must verify the interaction between the usage-stats capability and the rate-policy auto-block behavior.

### CR-006 — hypothesis
The example values (threshold 50, default block duration 300s) are illustrative; the actual threshold and default duration are configurable and their exact defaults are not yet confirmed as requirements.

### CR-007 — unknown
Exact existing Rate Limiter API surface (method names, stats structure, capability/policy registration mechanism) is unknown because product code was not read. These must be reconciled during analysis.

## Exclusions

No acceptance criteria, technical design, capability-routing decisions, or spec references are asserted here. These are reserved for later lifecycle phases.
