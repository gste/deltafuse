# TASK.md — S05: Usage Stats + Rate Policy

## Goal
Implement two new capabilities on `TokenBucketLimiter`:
1. `monitoring.usage_stats` — per-key usage statistics via `get_stats(key)`.
2. `security.rate_policy` — auto-block a key after N consecutive rejections.

## Files to change
- `src/ratelimit/limiter.py` — add stats tracking, `get_stats`, and policy blocking logic.
- `src/ratelimit/stats.py` — normalize stats with zero defaults.
- `src/ratelimit/policy.py` — policy config + threshold helper.
- `src/ratelimit/__init__.py` — export new helpers.
- `tests/test_limiter.py` — unit tests for stats and policy.
- `docs/spec/**` — normative (MUST) specs for both capabilities.

## Tests to add
- Stats: total/success/rejected counts for a key.
- Stats: zeros for unknown key.
- Stats: `peak_per_second` reflects max consume calls in any 1s window.
- Stats: `blocked_until` present while blocked, None after expiry.
- Policy: block triggers at threshold; `is_blocked` True during block.
- Policy: blocked `consume` returns False, no token deduction, counter not reset.
- Policy: block expires and normal behavior resumes.
- Integration: policy-blocked rejections counted in `rejected` stats.

## Out of scope
- No Change package, routing.yaml, coverage.yaml, FSM, or Decision files.
- No git push.
- No changes to unrelated baseline requirements (capacity/refill/consume semantics).
