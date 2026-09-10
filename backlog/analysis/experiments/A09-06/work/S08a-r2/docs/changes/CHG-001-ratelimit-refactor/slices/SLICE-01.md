---
id: SLICE-01
change: CHG-001-ratelimit-refactor
title: Introduce RateLimiterBackend abstraction with dependency injection
status: specified
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

- In scope: Extract `RateLimiterBackend` abstract interface (CR-001), move current in-memory implementation into `InMemoryBackend` (CR-002), inject backend into `RateLimiter` constructor (CR-003), move argument validation from backend into `RateLimiter` (CR-004).
- Out of scope: Modifying `docs/spec/security/ratelimit.md` (CR-007); adding new functionality (CR-006).

## Dependencies

- Requires locating the current `security.ratelimit` module under `src/ratelimit` and existing tests under `tests` (unknowns from request.md).

## Spec references

- `docs/spec/security/ratelimit.md` (REQ-RL-01..04) describes external behavior; must remain unchanged.

## Unchanged behavior

- External token-bucket contract preserved; only internal structure changes.

## Risks

- Import path changes may break existing tests (CR-005) — acceptable per claim.
- Validation move must not alter observable behavior.

## Context budget

- max_tokens: 4000, max_files: 8
