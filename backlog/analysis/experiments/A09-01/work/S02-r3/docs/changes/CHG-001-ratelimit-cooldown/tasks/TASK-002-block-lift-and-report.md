---
id: TASK-002
change: CHG-001-ratelimit-cooldown
slice: SLICE-01
kind: feature
status: pending
depends_on:
  - TASK-001
requirement_delta: added
spec_refs:
  - docs/spec/security/ratelimit.md#REQ-RL-06
  - docs/spec/security/ratelimit.md#REQ-RL-07
design_ref: null
allowed_paths:
  - src/ratelimit/limiter.py
  - tests/test_limiter.py
forbidden_paths:
  - docs/spec/auth/**
---

## Outcome
After `penalty_seconds` elapses, the block lifts automatically on the next
`consume` request and normal token-consumption logic resumes; `is_blocked(key)`
returns `True` while the key is under penalty and `False` otherwise.

## References
- SLICE-01, CR-005, CR-006
- `docs/spec/security/ratelimit.md#REQ-RL-06` (added), `#REQ-RL-07` (added)

## Steps
1. In `consume`, when a key's blocked end time has passed, clear the blocked
   state before resuming normal consumption logic (REQ-RL-06).
2. Ensure `is_blocked(key)` returns `True` while under penalty and `False`
   otherwise, including `False` for the baseline limiter (REQ-RL-04/REQ-RL-07).

## Test oracle
`tests/test_limiter.py`: after the penalty window elapses, a `consume` for the
previously blocked key returns `True` when tokens are available; `is_blocked`
returns `False` after lift and `True` during penalty; baseline limiter reports
`False` (REQ-RL-04).

## Unchanged behavior
Baseline limiter (no `penalty_seconds`) keeps prior rules exactly (CR-007).

## Verification
Run the limiter test suite for the block-lift and `is_blocked` paths; ensure
existing tests still pass unchanged.
