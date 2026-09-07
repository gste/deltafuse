---
id: TASK-004
change: CHG-001-ratelimit-refactor
slice: SLICE-01
kind: refactor
status: pending
depends_on:
  - TASK-003
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - src/ratelimit/
forbidden_paths:
  - docs/spec/security/ratelimit.md
  - tests/
---

# Move argument validation into RateLimiter

## Change / slice
CHG-001-ratelimit-refactor / SLICE-01

## Requirement / scenario refs
CR-005 (move argument validation from backend into `RateLimiter` as a single validation point).

## Outcome
`RateLimiter` performs all argument validation (e.g. capacity > 0, refill_rate >= 0) before delegating to the backend; the backend no longer performs validation.

## Steps
1. Identify validation currently performed inside the backend implementation.
2. Relocate that validation into `RateLimiter` (before backend delegation).
3. Remove validation from the backend so `RateLimiter` is the single validation point.

## Test oracle
Invalid arguments raise the same error types/messages as before the refactor; valid arguments behave identically (REQ-RL-01..04).

## Unchanged behavior
External contract per `docs/spec/security/ratelimit.md` REQ-RL-01..04 unchanged; observable error behavior preserved (CR-009).

## Verification
`python -m pytest tests/`

## Notes
Depends on TASK-003. Must not change observable validation behavior.
