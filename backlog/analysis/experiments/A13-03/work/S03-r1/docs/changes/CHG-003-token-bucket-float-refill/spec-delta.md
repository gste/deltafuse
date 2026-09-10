---
change: CHG-003-token-bucket-float-refill
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

The live spec `docs/spec/security/ratelimit.md` already requires proportional refill preserving fractional balances (REQ-RL-01) and correct consume debiting (REQ-RL-02). No normative behavior remains only in a request, Decision, design, or task; the Change is a code-only implementation fix. Specification unchanged.