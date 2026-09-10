---
id: SLICE-01
change: CHG-001-token-bucket-limiter
title: Token Bucket Rate Limiter core behavior
status: analyzing
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

- **In scope:** CR-001 through CR-004 — initialization with `capacity`/`refill_rate`, `consume(key, tokens=1)` returning a boolean, time-based proportional refill capped at `capacity`, and strict `ValueError` validation for non-positive `capacity`/`refill_rate` and `tokens <= 0`.
- **Out of scope:** Language/runtime/API conventions, persistence, concurrency/thread-safety, acceptance criteria/tests.

## Dependencies

- None.

## Spec references

- `docs/spec/_capabilities.yaml` (capability routing catalog; `rate-limiter` capability not yet defined).

## Unchanged behavior

- None; this is a new product.

## Risks

- Unknowns (language, persistence, concurrency) are non-blocking for this unambiguous feature; they will be resolved at implementation.

## Context budget

- `max_tokens: 4000`, `max_files: 8`.
