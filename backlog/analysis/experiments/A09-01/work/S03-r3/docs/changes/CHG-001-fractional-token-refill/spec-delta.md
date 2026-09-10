---
change: CHG-001-fractional-token-refill
status: proposed
slices:
  - SLICE-01
---

## ADDED

none

## MODIFIED

none

## REMOVED

none

## Rationale

`docs/spec/security/ratelimit.md` (REQ-RL-01 proportional refill preserving fractional balances; REQ-RL-02 consume debit) already governs the required behavior and is unchanged. The defect is an implementation deviation within `TokenBucketLimiter`; no normative spec change is required.