---
id: SLICE-01
change: CHG-001-ratelimit-consume-history
title: consume() attempt history and get_history()
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

- In scope: record an event per `consume(key, tokens)` call (key, timestamp, requested tokens, outcome `accepted`/`rejected`); add `get_history(key, n=10)` returning the last `n` events newest first; per-key isolation; `n` must be an integer `>= 1` (default 10, invalid raises); `consume` semantics unchanged.
- Out of scope: storage mechanism choice (CR-008, implementation detail); changes to token-bucket capacity/refill/consume results.

## Dependencies

- Requires existing `consume(key, tokens)` (CR-001) and the token-bucket contract in `docs/spec/security/ratelimit.md`.

## Spec references

- REQ-RL-02 (consume contract) — behavior preserved, not altered.
- REQ-RL-03 (unknown keys start full) — preserved.

## Unchanged behavior

- Token-bucket capacity, refill, and accept/reject results are identical with or without history (CR-007).

## Risks

- Timestamp source must be consistent and monotonic enough for ordering; storage must not interfere with consume performance or semantics.

## Delta projection

- specification: add REQ-RL for history recording and get_history contract.
- catalog: none.
- Decisions: none blocking (storage mechanism is an open implementation detail, CR-008).
- tasks: add history recording inside consume; implement get_history with validation.
- tests: per-key isolation, newest-first ordering, default n, invalid n raises, consume results unchanged.
- implementation: extend limiter with per-key event store.
- evidence: test run showing identical consume results with history enabled.
