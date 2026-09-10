---
id: SLICE-01
change: CHG-001-get-balance
title: Add get_balance() to security.ratelimit
status: specified
primary_capability: security.ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
  - CR-005
  - CR-006
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 6
---

## Scope

In scope: add `get_balance(key)` returning the current token balance without deduction.
Out of scope: changing `consume`, refill, or capacity semantics.

## Slice analysis

- **intent**: feature (additive method, no behavior change to existing operations).
- **delta_kind**: spec + implementation + tests.
- **requirement_delta**: new REQ-RL-05 defining `get_balance(key)` returns a non-negative integer equal to the key's current balance, with no deduction side effect; unknown keys start at full capacity (REQ-RL-03).
- **design_impact**: read-only accessor over the token-bucket state; must not mutate or partially deduct. Mirrors `consume` key initialization.
- **risk**: low. No side effects; constrained to one capability.
- **size**: small (single method + spec line + tests).

## Claims

- CR-001/CR-002: `get_balance(key)` returns current balance without deduction.
- CR-003: returns non-negative integer available for next `consume`.
- CR-004/CR-006: no side effects or partial deductions.
- CR-005: unknown key balance equals initial (full) capacity.

## Unknowns

Units of the initial limit are unspecified but are the same integer units as `consume`/capacity; not blocking for a single unambiguous feature.

## Next

Recommend `/decompose-change CHG-001-get-balance SLICE-01`.
