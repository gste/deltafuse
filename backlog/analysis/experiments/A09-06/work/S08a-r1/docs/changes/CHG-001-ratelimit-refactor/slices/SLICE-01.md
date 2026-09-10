---
id: SLICE-01
change: CHG-001-ratelimit-refactor
title: Extract backend abstraction and inject into RateLimiter
status: analyzing
primary_capability: ratelimit
related_capabilities:
  - architecture
  - testing
policies:
  - test-integrity
  - scope-discipline
  - spec-immutability
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
  - CR-008
  - CR-009
---

## Scope

In scope: refactor `security.ratelimit` (code root `src/ratelimit`) into a
`RateLimiterBackend` abstract interface with `init_key`, `consume`,
`get_balance`; move the in-memory implementation into `InMemoryBackend`;
inject the backend into `RateLimiter`'s constructor; move argument validation
into `RateLimiter`; keep all existing tests passing (import paths may change).

Out of scope: any new feature, behavior change, or edit to
`docs/spec/security/ratelimit.md`.

## Delta projection

- specification: none (REQ-RL-01..04 unchanged; external contract preserved).
- catalog: none.
- Decisions: none material beyond mechanical extraction.
- tasks: extraction, injection, validation move, test-path updates.
- tests: none authored; existing suite must pass unchanged except imports.
- implementation: refactor only; behavior-preserving.
- evidence: existing test suite green after refactor.

## Risks

- Import-path drift breaking tests if module layout changes; mitigate by
  updating imports per CR-006.
- Validation move must not alter observable behavior (CR-005, CR-009).

## Context budget

max_tokens: 4000, max_files: 12.
