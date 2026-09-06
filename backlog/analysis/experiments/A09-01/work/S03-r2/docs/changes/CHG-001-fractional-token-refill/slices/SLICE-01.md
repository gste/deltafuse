---
id: SLICE-01
change: CHG-001-fractional-token-refill
title: Fix fractional token refill accounting in TokenBucketLimiter
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
  - CR-007
---

## Scope

- In scope: `TokenBucketLimiter` refill accumulation (float, not integer division) and `consume` debit correctness for integer/fractional counts.
- Out of scope: any change to `docs/spec/security/ratelimit.md` (spec unchanged per CR-005).

## Delta

- `delta_kind`: bugfix
- `requirement_delta`: none (spec already requires proportional refill; no normative spec edit)
- `design_impact`: internal implementation only — refill state stored as float, no API/contract change
- `risk`: low (behavioral fix, no external contract change)
- `size`: small

## Dependencies

- None. Single capability slice.

## Risks

- Float precision across calls (CR-007) — resolve during analysis; not a blocking Decision.

## Context budget

- `max_tokens`: 4000
- `max_files`: 6