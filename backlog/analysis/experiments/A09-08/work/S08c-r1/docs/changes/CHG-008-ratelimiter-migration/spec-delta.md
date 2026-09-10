# Spec Delta — CHG-008-ratelimiter-migration

## Status

NONE

## Proof

`requirement_delta` is `none`. This Change relocates the Rate Limiter service
deployment coordinates (hostname `limiter-prod-01` → `limiter-prod-02`, port
`8080` → `9090`, log path `/var/log/ratelimiter/` → `/opt/logs/ratelimiter/`),
updates the monitoring health-check URL, and updates the ops runbook. None of
these are product behavior.

The normative spec `docs/spec/security/ratelimit.md` (REQ-RL-01..04) fully
covers the token-bucket limiter behavior and is unchanged:

- REQ-RL-01 Capacity and refill — unchanged
- REQ-RL-02 Consume — unchanged
- REQ-RL-03 Unknown keys — unchanged
- REQ-RL-04 is_blocked — unchanged

No ADDED, MODIFIED, or REMOVED requirements. No capability catalog delta.
No accepted Decision affecting observable behavior, contract, policy, or
required invariant.

## spec_refs

- docs/spec/security/ratelimit.md (REQ-RL-01..04) — token-bucket limiter behavior, sufficient