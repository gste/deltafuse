---
id: SLICE-01
change: CHG-001-ratelimit-cooldown
title: Optional cooldown penalty on TokenBucketLimiter
status: analyzing
primary_capability: ratelimit
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
---

## Scope

- In scope: `penalty_seconds` parameter, blocked state on failed consume, immediate `False` during window, auto-lift on next request, `is_blocked(key)`, backward compatibility.
- Out of scope: refill/capacity semantics (REQ-RL-01/02 unchanged), unknown-key defaults (REQ-RL-03 unchanged).

## Dependencies

- Baseline `TokenBucketLimiter` in `src/ratelimit` (code root from `_capabilities.yaml`).

## Spec references

- REQ-RL-01: capacity/refill unchanged.
- REQ-RL-02: consume behavior preserved when no penalty.
- REQ-RL-04: `is_blocked` MUST return False for baseline limiter — must be extended to report penalty state without breaking the no-penalty case.

## Unchanged behavior

- Non-penalty limiter behavior (CR-006): omitting `penalty_seconds` keeps prior rules.

## Risks

- CR-004/CR-005 unknowns: exact "next request" semantics for block removal not pinned; low materiality, resolve during implementation.
- `is_blocked` contract (REQ-RL-04) must not regress for baseline limiters.

## Context budget

- max_tokens: 4000, max_files: 6

## Typed delta

- intent: feature
- delta_kind: extension
- requirement_delta: extend REQ-RL-02/REQ-RL-04 with penalty behavior; add penalty requirements
- design_impact: add `penalty_seconds` field, blocked-state tracking, `is_blocked` state reporting
- risk: medium
- size: small