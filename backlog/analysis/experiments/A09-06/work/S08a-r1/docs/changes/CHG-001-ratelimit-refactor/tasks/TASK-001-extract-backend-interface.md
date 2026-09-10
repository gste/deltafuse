---
id: TASK-001
change: CHG-001-ratelimit-refactor
slice: SLICE-01
kind: refactor
status: pending
depends_on: []
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - src/ratelimit/
forbidden_paths:
  - docs/spec/security/ratelimit.md
  - tests/
---

# Extract RateLimiterBackend abstract interface

## Change / slice
CHG-001-ratelimit-refactor / SLICE-01

## Requirement / scenario refs
CR-002 (extract `RateLimiterBackend` abstract class with `init_key`, `consume`, `get_balance`).

## Outcome
A new abstract class `RateLimiterBackend` exists in `src/ratelimit` exposing exactly the methods `init_key`, `consume`, and `get_balance`, with no behavioral implementation of its own.

## Steps
1. Read the current `security.ratelimit` module under `src/ratelimit` to identify the existing `RateLimiter` class and the method bodies that correspond to `init_key`, `consume`, and `get_balance`.
2. Create `RateLimiterBackend` as an abstract base class (e.g. using `abc.ABC` / `@abstractmethod`) declaring `init_key`, `consume`, and `get_balance`.
3. Do not modify any existing behavior; only introduce the abstract interface.

## Test oracle
`python -c "from src.ratelimit.backend import RateLimiterBackend; import abc; assert issubclass(RateLimiterBackend, abc.ABC)"`
and instantiation of `RateLimiterBackend` directly raises `TypeError`.

## Unchanged behavior
External contract per `docs/spec/security/ratelimit.md` REQ-RL-01..04 is untouched; no production behavior changes.

## Verification
`python -m pytest tests/` (import paths may need updating in a later task; this task introduces no import changes to tests).

## Notes
This is the first ready task. Recommend `/target-task docs/changes/CHG-001-ratelimit-refactor/tasks/TASK-001-extract-backend-interface.md`.
