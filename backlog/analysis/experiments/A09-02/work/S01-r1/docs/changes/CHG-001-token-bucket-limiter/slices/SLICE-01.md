---
id: SLICE-01
change: CHG-001-token-bucket-limiter
title: Token Bucket Limiter Core
status: specified
primary_capability: limiter
related_capabilities: []
policies: []
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
context_budget:
  max_tokens: 8000
  max_files: 12
---

## Scope

- In scope: per-key token bucket with `capacity` and `refill_rate`, `consume(key, tokens=1)`, proportional time-based refill capped at `capacity`, strict `ValueError` validation.
- Out of scope: concurrency/thread-safety, time-source injection, persistence, key namespace scope, public API shape.

## Dependencies

- None. Foundational slice; no upstream slice required.

## Spec references

- `docs/spec/_capabilities.yaml` (capability routing catalog; populated for `limiter` and `validation`).
- `docs/spec/context.md` (product scope).
- `docs/spec/limiter/requirements.yaml` (RQ-001..RQ-005, SC-001..SC-007).

## Unchanged behavior

- None. New product, no existing behavior.

## Risks

- Unknowns (language, concurrency, time source, persistence) are non-blocking for this core slice; resolved as implementation choices, not product Decisions.

## Context budget

- 8000 tokens / 12 files reserved for this slice.
