---
id: SLICE-01
change: CHG-001-ratelimit-cooldown
title: Optional cooldown penalty on TokenBucketLimiter
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
  - CR-008
  - CR-009
---

## Scope

In scope: optional `penalty_seconds` constructor parameter (default `0.0`),
blocked-state transition on failed `consume`, immediate `False` while blocked,
automatic block lift after the penalty elapses, new `is_blocked(key)` method,
and backward compatibility for callers that omit `penalty_seconds`.

Out of scope: changing baseline capacity/refill semantics (REQ-RL-01/02/03),
any multi-service coordination, persistence, or concurrency handling beyond the
existing per-key state.

## Dependencies

- CR-008/CR-009: confirm actual per-key state tracking, token accumulation,
timing source, language, module path (`src/ratelimit`), and public API of
`security.ratelimit` before finalizing the delta.

## Spec references

- `docs/spec/security/ratelimit.md` REQ-RL-01..REQ-RL-04. REQ-RL-04 already
  fixes `is_blocked(key) == False` for the baseline limiter; the penalty feature
  extends behavior only when `penalty_seconds > 0`.

## Unchanged behavior

- Baseline limiter (no `penalty_seconds`) keeps prior rules exactly (CR-007).
- Capacity/refill and unknown-key defaults unchanged (REQ-RL-01/02/03).

## Risks

- Timing source mismatch (monotonic vs wall clock) could make the penalty
  window behave unexpectedly; confirm against existing code.
- Blocked-state storage must not interfere with existing per-key accounting.

## Context budget

- max_tokens: 4000, max_files: 8
