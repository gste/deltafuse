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
  - CR-007
---

## Scope

- **In scope:** Add optional `penalty_seconds` init param (default `0.0`); block a key on failed `consume`; force `consume` to return `False` while blocked; auto-lift block after the penalty window; add `is_blocked(key)`; preserve backward compatibility.
- **Out of scope:** Changes to capacity/refill semantics, concurrency/locking internals, or any non-`security.ratelimit` consumer.

## Slice analysis

- **intent:** feature (optional, opt-in behavior).
- **delta_kind:** requirement_delta + design_impact.
- **requirement_delta:** Extend `TokenBucketLimiter` with a penalty lock; add REQ-RL-05 (block semantics) and REQ-RL-06 (`is_blocked` under penalty). REQ-RL-04 already covers the no-penalty baseline.
- **design_impact:** Store per-key block expiry; gate `consume` on block state before token accounting; block timer starts at the failed `consume` call.
- **risk:** low-medium. Main uncertainty is penalty-window boundary semantics (CR-007), which is a non-blocking clarification, not a blocking Decision.
- **size:** small.

## Deltas

- **spec:** add REQ-RL-05, REQ-RL-06 (proposed, not accepted).
- **catalog:** none.
- **decisions:** none accepted; boundary semantics pending human clarification.
- **tasks/tests/implementation/evidence:** to be derived after analysis converges.

## Notes

All claims routed to `ratelimit` (see `routing.yaml`). CR-007 unknowns are clarifications, not blocking Decisions; status stays `continue`.