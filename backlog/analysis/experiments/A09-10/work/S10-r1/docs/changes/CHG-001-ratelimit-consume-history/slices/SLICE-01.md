---
id: SLICE-01
change: CHG-001-ratelimit-consume-history
title: Record consume() events and expose get_history(key, n)
status: analyzed
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
---

## Scope

In scope: record an event per `consume(key, tokens)` call; expose `get_history(key, n=10)` returning the last `n` events newest first; validate `n >= 1` integer (invalid raises); default `n=10`; per-key isolation.

Out of scope: storage backend selection (in-memory baseline), retention/eviction beyond returned slice, concurrency and durability guarantees.

## Dependencies

- None. Builds on existing `security.ratelimit.consume` (REQ-RL-02/03).

## Unchanged behavior

- `consume` return semantics (True/False, token deduction) are preserved (CR-005).
- Baseline limiter behavior (REQ-RL-01/02/03/04) is unchanged.

## Risks

- Recording overhead could alter performance characteristics; keep append cheap.
- History storage must not leak across keys.

## Context budget

- max_tokens: 4000
- max_files: 6
