# Request: Extend Rate Limiter with Usage Stats and Rate Policy Auto-Block

Source: `docs/intake/S05.md` (user request in Russian; summarized here).

## Summary

Two simultaneous changes are requested for the existing Rate Limiter product:

1. New capability `monitoring.usage_stats`: per-key usage statistics collection.
2. New policy `security.rate_policy`: automatic key blocking after a threshold of
   consecutive denied consumes.

Both changes must be mutually compatible, and integration tests must verify their
interaction.

## Claims

### CR-001 (expectation) — New capability `monitoring.usage_stats`

Add a capability that tracks, for each key:

- total number of `consume` calls,
- number of successful and denied requests,
- peak load (maximum number of calls per one second).

The method `get_stats(key)` must return a dictionary containing these values.

### CR-002 (expectation) — New policy `security.rate_policy`

Add a policy rule that, when the denial threshold is exceeded (e.g. 50 denied
`consume` calls in a row), automatically blocks the key for a configurable period
(default 300 seconds).

- A blocked key must return `False` from `consume` without consuming tokens.
- The blocked key's stats must contain a `blocked_until` marker.

### CR-003 (constraint) — Mutual compatibility

Both changes must be compatible with each other. Stats must correctly reflect
denials caused by both token shortage and by policy-based blocking.

### CR-004 (expectation) — Integration tests

Integration tests are required that verify the interaction between the two changes.

### CR-005 (observation) — Existing behavior preserved

The Rate Limiter product already exists; existing behavior must be preserved except
for the intentionally changed paths. No product code or spec was read during intake.

## Unknowns

- Exact key names / schema of the dict returned by `get_stats(key)` are not fully
  specified beyond the four documented values.
- The precise semantics of "50 denied consume in a row" (consecutive vs. total) is
  left as stated; may need clarification during analysis.
- Whether `blocked_until` is an absolute timestamp or a relative duration is not
  specified.
