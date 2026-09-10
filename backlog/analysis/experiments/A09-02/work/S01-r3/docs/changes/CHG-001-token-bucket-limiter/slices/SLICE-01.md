---
id: SLICE-01
change: CHG-001-token-bucket-limiter
title: Token Bucket Rate Limiter core
status: specified
primary_capability: rate-limiter
related_capabilities: []
policies: []
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
---

## Scope

In scope: per-key token bucket with `capacity`/`refill_rate`, `consume(key, tokens=1)` returning a boolean, time-proportional refill capped at `capacity`, and `ValueError` on invalid arguments.

Out of scope: persistence, concurrency/thread-safety, public API conventions, language/runtime selection, acceptance criteria/tests.

## Dependencies

None. Single capability (`rate-limiter`); all four claims are analytical slices of one bounded outcome.

## Spec references

- `docs/spec/_capabilities.yaml` — domain `rate-limiter`, capability `token-bucket`, requirements CR-001..CR-004.
- `docs/spec/rate-limiter/requirements.yaml` — CR-001..CR-004 with scenarios SC-001..SC-006.

## Unchanged behavior

None. Greenfield product; no existing behavior to preserve.

## Risks

Unknowns (language, persistence, concurrency, API conventions, acceptance criteria) are non-blocking for this unambiguous feature; they are deferred to implementation/slice decisions.

## Context budget

`max_tokens: 4000`, `max_files: 8`.

## Typed delta

- intent: feature
- delta_kind: new
- requirement_delta: add `rate-limiter` capability with CR-001..CR-004
- design_impact: none (implementation choice deferred)
- risk: low (logic is deterministic; unknowns are non-blocking)
- size: small
