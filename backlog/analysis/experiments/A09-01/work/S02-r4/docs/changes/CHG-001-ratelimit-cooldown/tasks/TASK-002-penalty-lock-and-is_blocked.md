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
  - docs/spec/security/ratelimit.md#REQ-RL-05
  - docs/spec/security/ratelimit.md#REQ-RL-06
design_ref: null
allowed_paths:
  - src/ratelimit/limiter.py
  - tests/test_limiter.py
forbidden_paths:
  - docs/spec/auth/**
---

# TASK-002 — Penalty lock block + `is_blocked` under penalty

## Outcome
When `penalty_seconds > 0`, a failed `consume` transitions the key into a blocked state lasting `penalty_seconds`; while blocked `consume` returns `False` immediately even if tokens accumulated; the block auto-clears after the window on the next request; `is_blocked(key)` returns `True` under penalty and `False` otherwise.

## References
- Change/slice: CHG-001-ratelimit-cooldown / SLICE-01
- `docs/spec/security/ratelimit.md#REQ-RL-05` (penalty lock semantics)
- `docs/spec/security/ratelimit.md#REQ-RL-06` (`is_blocked` under penalty)

## Design notes (do not hard-code as law)
- Store per-key block expiry; gate `consume` on block state before token accounting.
- Block timer starts at the failed `consume` call (per slice analysis).
- Boundary semantics (inclusive vs exclusive) and concurrency interactions are non-blocking clarifications (CR-007); pick a consistent interpretation and document it in the test oracle.

## Test oracle
- With `penalty_seconds > 0`, a `consume` that lacks tokens returns `False` and `is_blocked(key)` returns `True`.
- While blocked, a `consume` returns `False` immediately even after tokens would have accumulated.
- After the penalty window elapses, the next `consume` resumes normal spending logic and `is_blocked(key)` returns `False`.
- `is_blocked(key)` for a never-blocked key returns `False`.

## Unchanged behavior
- Baseline limiter (no `penalty_seconds`) must still return `False` from `is_blocked` (REQ-RL-04) and preserve prior `consume` rules (REQ-RL-02, CR-006).

## Allowed / forbidden
- Allowed: `src/ratelimit/limiter.py`, `tests/test_limiter.py`
- Forbidden: `docs/spec/auth/**`

## Verification
- Run `pytest tests/test_limiter.py` and confirm penalty-lock and `is_blocked` cases pass without regressing baseline behavior.
