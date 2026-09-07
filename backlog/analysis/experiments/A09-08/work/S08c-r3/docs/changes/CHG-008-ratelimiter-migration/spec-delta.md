---
change: CHG-008-ratelimiter-migration
status: proposed
slices:
  - SLICE-01
---

# Spec Delta — CHG-008-ratelimiter-migration

## requirement_delta: none

The token-bucket rate limiting behavior described in `docs/spec/security/ratelimit.md` (REQ-RL-01 through REQ-RL-04) is unchanged. Service deployment coordinates are operational concerns, not product behavioral requirements.

## spec_refs (sufficiency proof)

- `docs/spec/security/ratelimit.md` — behavioral spec for the rate limiter; unaffected by server migration. No REQ-RL delta required.

## ADDED

- (none)

## MODIFIED

- (none)

## REMOVED

- (none)
