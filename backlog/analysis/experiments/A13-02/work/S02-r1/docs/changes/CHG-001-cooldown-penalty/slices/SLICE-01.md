---
id: SLICE-01
change: CHG-001-cooldown-penalty
title: Optional cooldown penalty on TokenBucketLimiter
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

- **In scope:** Add optional `penalty_seconds` (default `0.0`) to `TokenBucketLimiter` init; on failed `consume` with `penalty_seconds > 0`, transition key to a blocked state for `penalty_seconds`; block returns `False` immediately during penalty; block lifts on next request after elapse; add `is_blocked(key)`; preserve backward compatibility.
- **Out of scope:** Changes to capacity/refill semantics (REQ-RL-01/02/03), non-penalty behavior, other limiters.

## Dependencies

- Baseline `TokenBucketLimiter` contract in `docs/spec/security/ratelimit.md` (REQ-RL-01..04).
- `is_blocked` already declared (REQ-RL-04) — must now report penalty state.

## Spec references

- REQ-RL-02 consume contract — must honor block before token check.
- REQ-RL-03 unknown keys start full — unaffected by penalty logic.
- REQ-RL-04 `is_blocked` — baseline returns `False`; extended to report penalty.
- REQ-RL-05..08 — new penalty requirements.

## Unchanged behavior

- `penalty_seconds == 0` (default) preserves prior behavior exactly (CR-006).
- Capacity/refill and unknown-key handling unchanged.

## Risks

- CR-007 unknowns: exact interaction of penalty with partial token accumulation after block lifts, and whether `is_blocked` is independently observable/testable. Not blocking — left for later analysis; baseline `is_blocked` remains `False` when no penalty applies.

## Typed delta

- **intent:** feature
- **delta_kind:** additive
- **requirement_delta:** extend `docs/spec/security/ratelimit.md` with penalty requirements (blocked-state transition, immediate `False` during penalty, auto-lift, `is_blocked` reporting).
- **design_impact:** `TokenBucketLimiter` state must track per-key penalty expiry; new public method `is_blocked(key)`.
- **risk:** medium (behavior change to consume path; backward-compat constraint).
- **size:** small

## Delta projection

- **specification:** add penalty requirements under `security.ratelimit`.
- **catalog:** none.
- **Decisions:** none required — single unambiguous feature; unknowns are not blocking.
- **tasks:** init param, blocked-state tracking, consume block check, `is_blocked`, backward-compat tests.
- **tests:** blocked consume returns `False`, auto-lift after elapse, `is_blocked` reporting, no-penalty baseline unchanged.
- **implementation:** `src/ratelimit`.
- **evidence:** spec-aligned test run.
