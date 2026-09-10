---
id: SLICE-01
change: CHG-001-ratelimit-refactor
title: Extract RateLimiterBackend abstraction with dependency injection
status: analyzing
primary_capability: ratelimit
related_capabilities:
  - architecture
  - testing
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
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 8
---

## Scope

- **In scope:** Extract `RateLimiterBackend` abstract interface (CR-002); move in-memory impl into `InMemoryBackend` (CR-003); inject backend into `RateLimiter` constructor (CR-004); move argument validation into `RateLimiter` (CR-005).
- **Out of scope:** Any change to `docs/spec/security/ratelimit.md` (CR-008); new functionality (CR-007).

## Slice analysis

- **intent:** refactor — behavior-preserving restructuring only.
- **delta_kind:** internal-structure.
- **requirement_delta:** none; external contract preserved.
- **design_impact:** new abstract base `RateLimiterBackend` with `init_key`, `consume`, `get_balance`; `RateLimiter` gains a constructor backend parameter; validation relocated to `RateLimiter`.
- **risk:** low-medium — import-path changes may break existing tests (CR-006); validation-move must not alter behavior (CR-005).
- **size:** small.

## Dependencies

- Reads `src/ratelimit` module and `tests/` suite to confirm current structure (CR-010 unknown).
- CR-009 is a hypothesis to confirm via existing tests, not an established fact.

## Context budget

4000 tokens / 8 files: read module source, backend impl, and test files only.