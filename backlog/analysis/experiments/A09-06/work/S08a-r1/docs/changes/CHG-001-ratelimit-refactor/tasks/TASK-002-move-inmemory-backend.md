---
id: TASK-002
change: CHG-001-ratelimit-refactor
slice: SLICE-01
kind: refactor
status: pending
depends_on:
  - TASK-001
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - src/ratelimit/
forbidden_paths:
  - docs/spec/security/ratelimit.md
  - tests/
---

# Move in-memory implementation into InMemoryBackend

## Change / slice
CHG-001-ratelimit-refactor / SLICE-01

## Requirement / scenario refs
CR-003 (move in-memory implementation into `InMemoryBackend` implementing `RateLimiterBackend`).

## Outcome
The existing in-memory token-bucket implementation is relocated into a class `InMemoryBackend` that subclasses `RateLimiterBackend` and implements `init_key`, `consume`, and `get_balance` with behavior identical to the original in-memory code.

## Steps
1. In the current module, identify the in-memory token-bucket state and logic.
2. Create `InMemoryBackend(RateLimiterBackend)` containing that logic.
3. Remove the in-memory implementation from its original location, leaving only the abstract interface (from TASK-001) in place.

## Test oracle
`InMemoryBackend` instances behave identically to the original in-memory limiter for the same inputs (same consume/balance outcomes per REQ-RL-01..04).

## Unchanged behavior
External contract per `docs/spec/security/ratelimit.md` REQ-RL-01..04 unchanged; behavior-preserving (CR-009).

## Verification
`python -m pytest tests/`

## Notes
Depends on TASK-001 for the abstract interface. Validation move is a separate task (TASK-003).
