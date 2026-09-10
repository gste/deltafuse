---
change: CHG-001-fractional-token-refill
status: proposed
slices:
  - SLICE-01
---

## Delta

- ADDED: none
- MODIFIED: none
- REMOVED: none

## Rationale

`docs/spec/security/ratelimit.md` already requires proportional refill preserving fractional balances (REQ-RL-01) and correct consume debit (REQ-RL-02). The bug is an implementation defect (integer division discarding fractional accrual), not a specification gap. No normative spec behavior is added, modified, or removed. Acceptance is proven by exact spec_refs: `docs/spec/security/ratelimit.md` (REQ-RL-01, REQ-RL-02).