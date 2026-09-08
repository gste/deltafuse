# Spec Delta — CHG-001-get-balance

Slice: SLICE-01
Delta kind: capability_addition

## ADDED

- REQ-RL-05 (docs/spec/security/ratelimit.md): get_balance(key) MUST return the current available token count for key as a non-negative integer without deducting tokens or creating any deduction side effect.
- REQ-RL-06 (docs/spec/security/ratelimit.md): get_balance(key) MUST NOT modify token accounting, refill state, or capacity for key or any other key.
