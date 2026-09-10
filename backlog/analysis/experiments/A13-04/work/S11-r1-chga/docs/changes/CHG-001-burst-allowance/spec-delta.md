---
change: CHG-001-burst-allowance
status: accepted
slices:
  - SLICE-01
added:
  - docs/spec/security/ratelimit.md#req-rl-05
modified: []
removed: []
---

# Spec Delta — CHG-001-burst-allowance

Scope: SLICE-01 (Optional burst_allowance retry in TokenBucketLimiter.consume)

## ADDED

- REQ-RL-05: `docs/spec/security/ratelimit.md` — per-key `burst_allowance` retry clause (already present in live spec; asserted as the normative anchor for CR-002/CR-003/CR-004/CR-005).

## MODIFIED

- none

## REMOVED

- none
