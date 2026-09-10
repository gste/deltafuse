---
id: TASK-005
change: CHG-001-ratelimit-refactor
slice: SLICE-01
kind: refactor
status: pending
depends_on:
  - TASK-004
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - src/ratelimit/
  - tests/
forbidden_paths:
  - docs/spec/security/ratelimit.md
---

# Update import paths so existing tests pass

## Change / slice
CHG-001-ratelimit-refactor / SLICE-01

## Requirement / scenario refs
CR-006 (all existing tests must pass unchanged except import paths).

## Outcome
All existing tests import from the new module layout and pass; no test assertions or logic were modified.

## Steps
1. Run the existing test suite after TASK-001..004 to identify import failures caused by the module layout change.
2. Update only import statements in `tests/` to reference the new locations (e.g. `InMemoryBackend`, `RateLimiterBackend`, `RateLimiter`).
3. Do not modify any test assertions, fixtures, or logic.

## Test oracle
`python -m pytest tests/` passes fully with only import-statement changes in `tests/`.

## Unchanged behavior
No test logic modified (CR-006); external contract per `docs/spec/security/ratelimit.md` REQ-RL-01..04 unchanged.

## Verification
`python -m pytest tests/`

## Notes
Final task; depends on the full refactor chain. Verify no behavioral changes were introduced beyond import paths.
