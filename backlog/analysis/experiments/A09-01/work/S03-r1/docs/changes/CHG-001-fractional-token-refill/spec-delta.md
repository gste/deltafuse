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

## Notes

`docs/spec/security/ratelimit.md` already mandates proportional refill preserving fractional balances (REQ-RL-01) and correct consume debit (REQ-RL-02). The defect is an implementation issue in `TokenBucketLimiter`, not a specification gap. No normative spec change is required; `spec_refs` in coverage.yaml document sufficiency.