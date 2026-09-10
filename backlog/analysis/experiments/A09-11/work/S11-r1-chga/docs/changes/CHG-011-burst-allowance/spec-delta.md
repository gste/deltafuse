---
change: CHG-011-burst-allowance
status: accepted
slices:
  - SLICE-01
added:
  - REQ-RL-05
modified:
  - docs/spec/security/ratelimit.md
removed: []
---

# Spec Delta — CHG-011-burst-allowance

## Added

- REQ-RL-05 (docs/spec/security/ratelimit.md): TokenBucketLimiter MAY initialize with an optional `burst_allowance` (default 0). While a key has unused `burst_allowance` tokens, a rejected `consume` MUST grant `extra` tokens once and retry the attempt within the same call. When `burst_allowance` is 0, `consume` behaves as REQ-RL-02 with no retry.

## Modified

- docs/spec/security/ratelimit.md: added REQ-RL-05 section.

## Removed

- (none)
