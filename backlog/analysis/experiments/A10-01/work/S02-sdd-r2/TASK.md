# TASK.md: Cool-down penalty for rate limiter

## Goal
Add optional `penalty_seconds` to `TokenBucketLimiter` so a failed `consume` blocks the key for the penalty duration.

## Files to change
- `src/ratelimit/limiter.py`: add `penalty_seconds` param, implement block state in `consume` and `is_blocked`.
- `tests/test_limiter.py`: add tests for penalty behavior (block on failure, immediate False while blocked, auto-clear after penalty, is_blocked, backward compat).

## Tests to add
- Failed consume enters blocked state; is_blocked True.
- consume returns False immediately while blocked even with accumulated tokens.
- After penalty_seconds elapses, block clears and normal consume resumes.
- Baseline (no penalty) still returns False from is_blocked.

## Out of scope
- Persistence, per-key penalties, config/routing files, docs beyond spec.
