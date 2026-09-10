---
id: SLICE-01
change: CHG-001-get-balance
title: Add read-only get_balance() to security.ratelimit
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
depends_on: []
---

## Scope

In scope: a read-only `get_balance(key)` method on the token-bucket limiter that returns the current available token count without deducting or creating side effects.

Out of scope: any mutation of token accounting, refill/capacity policy changes, and key-initialization semantics beyond what REQ-RL-03 already fixes.

## Dependencies

- REQ-RL-03 defines unknown-key behavior (starts at full capacity), which fixes CR-004's unknown initial-limit question.
- REQ-RL-02/REQ-RL-01 constrain what "balance" means (capacity minus consumed, never negative).

## Spec references

- `docs/spec/security/ratelimit.md`: REQ-RL-01 (capacity/refill), REQ-RL-02 (consume semantics), REQ-RL-03 (unknown keys at full capacity), REQ-RL-05 (read-only balance accessor), REQ-RL-06 (read-only guarantee).

## Unchanged behavior

- `consume`, `is_blocked`, capacity, and refill semantics are unchanged; this slice adds only a read accessor.

## Risks

- Balance must clamp at 0 and never go negative (CR-002).
- Must not touch refill state or create deduction side effects (CR-003, CR-005).

## Context budget

- max_tokens: 4000, max_files: 8

## Typed delta

- intent: feature
- delta_kind: capability_addition
- requirement_delta: add REQ-RL-05 (read-only balance accessor)
- design_impact: add public method to `security.ratelimit`; no new state
- risk: low
- size: small
