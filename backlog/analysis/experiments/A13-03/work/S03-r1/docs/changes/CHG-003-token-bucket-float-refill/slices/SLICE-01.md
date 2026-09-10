---
id: SLICE-01
change: CHG-003-token-bucket-float-refill
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
---

## In scope
- Refill accumulates tokens as `float` so fractional parts persist across calls (CR-002).
- `consume` debits integer or fractional token counts correctly (CR-003).
- Red test reproducing fractional-token accrual at small time intervals (CR-005).

## Out of scope
- Any change to `docs/spec/security/ratelimit.md` (CR-004, spec unchanged).
- Capacity/refill_rate validation (already covered by REQ-RL-01).

## Dependencies
- None; single capability `ratelimit`.

## Spec references
- REQ-RL-01: proportional refill preserving fractional balances.
- REQ-RL-02: consume deducts tokens when available.

## Unchanged behavior
- REQ-RL-03 (unknown keys start full), REQ-RL-04 (is_blocked baseline).

## Risks
- Test timing must be deterministic (inject elapsed time) to avoid flakiness.

## Context budget
- max_tokens: 16000, max_files: 24

## Typed delta
- intent: fix lost fractional accrual in refill accounting.
- delta_kind: implementation + test.
- requirement_delta: none (spec unchanged).
- design_impact: internal token storage becomes float; consume accepts float debit.
- risk: low.
- size: small.