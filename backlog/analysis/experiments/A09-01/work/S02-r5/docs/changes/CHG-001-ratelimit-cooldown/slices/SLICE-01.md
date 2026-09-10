---
id: SLICE-01
change: CHG-001-ratelimit-cooldown
title: Optional cooldown penalty on TokenBucketLimiter.consume
status: analyzing
primary_capability: security.ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-002
  - CR-003
  - CR-004
  - CR-005
  - CR-006
  - CR-007
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 6
---

## Scope

- **In scope:** Add optional `penalty_seconds` init param (default `0.0`); on failed `consume` when `penalty_seconds > 0`, place key in a blocked state lasting `penalty_seconds`; while blocked, `consume` returns `False` immediately even with accumulated tokens; auto-lift block on next request after penalty elapses; add `is_blocked(key)`; preserve prior behavior when `penalty_seconds` absent.
- **Out of scope:** Changes to capacity/refill semantics (REQ-RL-01/02/03), unknown-key handling, and any non-`security.ratelimit` callers.

## Dependencies

- Requires reading `src/ratelimit` to confirm language, per-key state storage, and clock source (CR-009).
- Must confirm blocked-vs-insufficient-token semantics and accrual interaction (CR-008).

## Spec references

- `docs/spec/security/ratelimit.md`: REQ-RL-01 (capacity/refill unchanged), REQ-RL-02 (consume contract), REQ-RL-03 (unknown keys start full), REQ-RL-04 (`is_blocked` baseline returns False).

## Unchanged behavior

- Baseline limiter with no `penalty_seconds` keeps prior rules; `is_blocked` returns `False` (REQ-RL-04).
- Capacity > 0 and refill_rate >= 0 invariants (REQ-RL-01).

## Risks

- Clock source mismatch could make penalty timing incorrect; confirm monotonic vs wall-clock.
- Per-key state storage must survive across `consume` calls; verify lifetime and cleanup.
- Accrual during penalty window must not lift the block; ensure block check precedes token check.

## Context budget

- `max_tokens: 4000`, `max_files: 6` — read only `src/ratelimit` implementation, `docs/spec/security/ratelimit.md`, and related Decisions.

## Typed delta

- **intent:** feature
- **delta_kind:** additive
- **requirement_delta:** add REQ-RL-05 (penalty block semantics) and REQ-RL-06 (`is_blocked` under penalty); REQ-RL-04 extended to report penalty blocks.
- **design_impact:** `TokenBucketLimiter.__init__` gains `penalty_seconds`; per-key state gains blocked timestamp; `consume` gains block short-circuit; new `is_blocked` method.
- **risk:** medium
- **size:** small