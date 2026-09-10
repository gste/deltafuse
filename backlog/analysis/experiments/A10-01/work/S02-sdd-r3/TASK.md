# TASK.md: Cool-down penalty for TokenBucketLimiter

## Files to change
- `src/ratelimit/limiter.py` — add optional `penalty_seconds` param, implement blocked-state logic and `is_blocked`.
- `tests/test_limiter.py` — add tests for penalty behavior.
- `docs/spec/security/ratelimit.md` — REQ-RL-05 is already normative; keep as-is.

## Tests to add
- Failed consume with `penalty_seconds > 0` makes `is_blocked(key)` True.
- `consume` returns False immediately during block even if tokens accumulated.
- Block clears after `penalty_seconds` elapses; normal token logic resumes.
- Baseline limiter (no penalty) keeps `is_blocked` always False (existing test).
- Backward compatibility: existing behavior unchanged when `penalty_seconds=0.0`.

## Out of scope
- Persistence across process restarts.
- Per-key penalty durations.
- Any routing/Change package files.
