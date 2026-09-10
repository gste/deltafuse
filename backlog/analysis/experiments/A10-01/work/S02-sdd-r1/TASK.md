# TASK.md — S02 Cool-down penalty for TokenBucketLimiter

## Goal
Add optional `penalty_seconds` lock to `TokenBucketLimiter` when a `consume` fails for lack of tokens.

## Files to change
- `src/ratelimit/limiter.py` — accept `penalty_seconds` (default 0.0); store a lock expiry per key; block `consume` while locked; implement `is_blocked`.
- `tests/test_limiter.py` — add tests for penalty lock, auto-release, and `is_blocked`.

## Tests to add
- Failed consume with `penalty_seconds > 0` returns False and `is_blocked` True.
- While locked, consume returns False even after tokens accumulate.
- After penalty elapses, consume resumes normally and `is_blocked` becomes False.
- Baseline (penalty_seconds == 0) keeps existing behaviour; `is_blocked` always False.

## Out of scope
- Persistence across restarts, per-key penalty durations, clock injection (use `time.monotonic`).
- Any routing/coverage/FSM/Decision artifacts.
