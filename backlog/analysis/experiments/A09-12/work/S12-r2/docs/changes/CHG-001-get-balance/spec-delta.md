---
change: CHG-001-get-balance
status: accepted
slices:
  - SLICE-01
added:
  - REQ-RL-05
modified: []
removed: []
---

# Spec Delta — CHG-001-get-balance

## ADDED

- REQ-RL-05 (docs/spec/security/ratelimit.md): `get_balance(key)` MUST return the current non-negative token balance for key without deducting tokens or producing any deduction side effect. For an unknown key, the returned balance equals the initial full capacity.

## MODIFIED

- None

## REMOVED

- None
