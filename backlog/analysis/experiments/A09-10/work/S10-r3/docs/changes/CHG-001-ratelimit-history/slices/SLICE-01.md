---
id: SLICE-01
change: CHG-001-ratelimit-history
title: Record consume events and expose get_history
status: specified
primary_capability: ratelimit
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

- In scope: record an event per `consume(key, tokens)` call with key, timestamp, requested token count, and outcome; add `get_history(key, n=10)` returning the last `n` events newest first; validate `n` (integer >= 1, exception otherwise); default `n=10`; per-key isolation; no change to `consume` semantics.
- Out of scope: storage backend selection, retention limits, persistence, and the pre-existing `consume`/`is_blocked` contract (CR-001 observation only).

## Dependencies

- Requires the existing `consume(key, tokens)` method (CR-001) to remain behaviorally identical.

## Spec references

- REQ-RL-01: capacity and refill baseline (unchanged).
- REQ-RL-02: `consume` result semantics unchanged.
- REQ-RL-03: unknown keys start at full capacity (unchanged).
- REQ-RL-04: `is_blocked` baseline contract (unchanged).
- REQ-RL-05: per-event record shape.
- REQ-RL-06: `get_history` contract.
- REQ-RL-07: `n` validation.
- REQ-RL-08: default `n=10`.
- REQ-RL-09: per-key isolation.
- REQ-RL-10: semantic invariance of `consume`.

## Unchanged behavior

- Token-bucket capacity, refill, deduction, and return values are identical with history enabled.

## Risks

- Recording overhead must not alter timing-sensitive limiter behavior.
- Timestamp source must be consistent and monotonic enough for ordering.

## Delta projection

- specification: REQ-RL-05 through REQ-RL-10 added.
- catalog: none.
- Decisions: none blocking (backend/retention are CR-008 open, non-blocking).
- tasks: add history recording in `consume` and `get_history` implementation.
- tests: per-event recording, newest-first ordering, `n` validation, default, per-key isolation, semantic equivalence.
- evidence: behavior tests against REQ deltas.

## Context budget

- 4000 tokens / 6 files; single bounded slice.
