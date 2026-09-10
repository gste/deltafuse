---
id: TASK-003
change: CHG-001-ratelimit-refactor
slice: SLICE-01
kind: refactor
status: pending
depends_on:
  - TASK-002
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - src/ratelimit/
forbidden_paths:
  - docs/spec/security/ratelimit.md
  - tests/
---

# Inject backend into RateLimiter constructor

## Change / slice
CHG-001-ratelimit-refactor / SLICE-01

## Requirement / scenario refs
CR-004 (`RateLimiter` accepts a backend via dependency injection in its constructor).

## Outcome
`RateLimiter`'s constructor accepts a `RateLimiterBackend` instance and delegates `init_key`/`consume`/`get_balance` to it; no backend is constructed internally.

## Steps
1. Modify `RateLimiter.__init__` to accept a `backend` parameter typed as `RateLimiterBackend`.
2. Route `RateLimiter`'s operations through `self.backend`.
3. Ensure the default/expected usage still constructs an `InMemoryBackend` where the module previously did so (internal wiring only).

## Test oracle
`RateLimiter(backend=InMemoryBackend(...))` produces identical observable behavior to the pre-refactor `RateLimiter` for the same inputs (REQ-RL-01..04).

## Unchanged behavior
External contract per `docs/spec/security/ratelimit.md` REQ-RL-01..04 unchanged; behavior-preserving (CR-009).

## Verification
`python -m pytest tests/`

## Notes
Depends on TASK-002. Validation move is a separate task (TASK-003's sibling TASK-004).
