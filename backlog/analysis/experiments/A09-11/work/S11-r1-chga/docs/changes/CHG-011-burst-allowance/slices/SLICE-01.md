---
id: SLICE-01
change: CHG-011-burst-allowance
title: Add optional burst_allowance to TokenBucketLimiter
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
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 6
---

## Scope

- **In scope:** Optional `burst_allowance` init parameter (default 0); on a rejected `consume`, grant `extra` tokens once and retry within the same call while unused burst tokens remain; preserve existing consume/refill semantics.
- **Out of scope:** Changes to capacity/refill contract, is_blocked behavior, or other capabilities.

## Dependencies

- Existing `TokenBucketLimiter` API in `src/ratelimit` (language/module to be confirmed; CR-005).

## Spec references

- `docs/spec/security/ratelimit.md`: REQ-RL-01 (capacity/refill), REQ-RL-02 (consume), REQ-RL-03 (unknown keys), REQ-RL-04 (is_blocked), REQ-RL-05 (burst retry).

## Unchanged behavior

- Default `burst_allowance = 0` preserves current consume/refill behavior (CR-003).

## Risks

- Retry grant semantics unspecified: exact `extra` amount, whether partial grants are allowed, and whether the grant consumes from `burst_allowance` (CR-004).
- Target language/module/API not yet confirmed (CR-005).

## Context budget

- ~4000 tokens, ~6 files: read `ratelimit.md`, locate `TokenBucketLimiter`, inspect existing consume, then stop.

## Typed delta

- **intent:** feature
- **delta_kind:** additive
- **requirement_delta:** add REQ-RL-05 describing burst retry behavior (pending CR-004/CR-005 resolution)
- **design_impact:** constructor signature gains optional `burst_allowance`; consume gains one-shot retry path
- **risk:** low
- **size:** small
