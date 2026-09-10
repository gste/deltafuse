# TASK.md — S05: Usage Stats + Rate Policy

## Goal
Extend `TokenBucketLimiter` with per-key usage statistics (`monitoring.usage_stats`) and a block-on-threshold policy (`security.rate_policy`), both reflected in `get_stats`.

## Files to change
- `src/ratelimit/limiter.py` — add stats tracking, consecutive-reject counter, policy block logic, `get_stats(key)`, `reject_threshold` and `block_duration` constructor params.
- `tests/test_limiter.py` — add unit tests for stats, peak load, policy block, and integration tests for both changes working together.
- `docs/spec/**` — already normative (MUST) in the provided specs; keep baseline REQ-RL-01..04.

## Tests to add
- Stats: total/success/rejected counts for a key.
- `get_stats` returns zeros for unknown key.
- `peak_per_second` reflects max consume calls in any 1s window.
- Both token-insufficient and policy-blocked rejections counted in `rejected`.
- Policy: block after `reject_threshold` consecutive rejections; `is_blocked` True, `consume` False without token deduction; `blocked_until` set.
- Successful consume resets consecutive-reject counter.
- Integration: stats correctly reflect rejections caused by both token shortage and policy block.

## Out of scope
- No Change package, routing.yaml, coverage.yaml, FSM statuses, or Decision files.
- No git push.
- No changes to unrelated baseline requirements.
