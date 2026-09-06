---
id: SLICE-01
change: CHG-001-fractional-token-refill
title: Fractional token refill accumulation and consume debit
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

## Slice analysis

### Scope

- In scope: `TokenBucketLimiter` refill math in `src/ratelimit`; `consume` debit correctness for integer and fractional token amounts.
- Out of scope: spec edits to `docs/spec/security/ratelimit.md` (must remain unchanged, CR-005); penalty-lock / `is_blocked` behavior (CR-006 test only).

### Dependencies

- Requires the existing `TokenBucketLimiter` implementation under `src/ratelimit`.
- CR-006 test creation is a downstream Target-phase task; this slice only records the expectation.

### Spec references

- `docs/spec/security/ratelimit.md` REQ-RL-01 (proportional refill, preserve fractional balances), REQ-RL-02 (consume debit).

### Unchanged behavior

- REQ-RL-03 (unknown keys start at full capacity) and REQ-RL-04 (`is_blocked` returns False) are unaffected.

### Risks

- Regression if refill clamps fractional accrual; must not exceed capacity.
- `consume` must reject partial debit when insufficient tokens (REQ-RL-02).

### Context budget

- ~4000 tokens, 6 files: spec, limiter source, existing tests.

### Typed delta

- intent: fix integer-division refill to float accumulation (CR-002, CR-003).
- delta_kind: implementation.
- requirement_delta: none (spec already mandates proportional refill; CR-005).
- design_impact: internal state type for pending tokens becomes float.
- risk: medium (regression on debit correctness).
- size: small.

### Delta projection

- specification: none.
- catalog: none.
- Decisions: none.
- tasks: none.
- tests: none yet (CR-006 is Target-phase).
- implementation: refill accumulates float; consume debits integer/fractional correctly.
- evidence: Red test at Target phase reproducing fractional accrual at small intervals (CR-006).