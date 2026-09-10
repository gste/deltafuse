# Request: Extend Rate Limiter with usage stats and rate policy

Source: `docs/intake/S05.md` (repository file under configured `paths.intake`).

## Summary

The Rate Limiter product must be extended with two simultaneous changes:

1. A new capability `monitoring.usage_stats` that collects per-key usage
   statistics (total `consume` calls, successful and denied counts, and peak
   load / max calls per second) and exposes them through `get_stats(key)`.
2. A new policy `security.rate_policy` that automatically blocks a key for a
   configurable period (default 300s) once a configurable threshold of
   consecutive denied consumes (e.g. 50) is exceeded. A blocked key returns
   `False` from `consume` without consuming tokens and carries a `blocked_until`
   field in its stats.

Both changes must be mutually compatible: stats must correctly reflect denials
caused by both token exhaustion and policy-based blocking. Integration tests
verifying the interaction of both changes are required.

## Claims

### CR-001 — observation
The source is a repository file located at `docs/intake/S05.md`. Its path is
preserved in provenance; the file remains in place (not moved) until the
immutable request is complete.

### CR-002 — expectation
A new capability `monitoring.usage_stats` must be added. For each key it must
track: total number of `consume` calls, number of successful consumes, number
of denied consumes, and peak load (maximum number of calls in a single second).
`get_stats(key)` must return a dictionary containing these values.

### CR-003 — expectation
A new policy `security.rate_policy` must be added. When the number of
consecutive denied `consume` calls exceeds a configurable threshold (example
value 50), the key must be automatically blocked for a configurable period
(default 300 seconds). While blocked, `consume` must return `False` without
consuming tokens, and the key's stats must include a `blocked_until` marker.

### CR-004 — constraint
Both changes must be compatible with each other. Usage stats must correctly
reflect denials caused by both token exhaustion and policy-based blocking.

### CR-005 — expectation
Integration tests must be provided that verify the interaction between the
usage-stats capability and the rate policy.

### CR-006 — hypothesis
The example values in the source (threshold 50, default block period 300s) are
illustrative; the actual configurable defaults and thresholds are unspecified
and left as open parameters.

### CR-007 — constraint
No acceptance criteria, technical design, capability routing details, or spec
references are invented here; these are deferred to later lifecycle phases.
