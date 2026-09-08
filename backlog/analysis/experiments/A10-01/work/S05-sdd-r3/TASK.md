# TASK.md — S05: Usage Stats + Rate Policy

## Goal
Implement two capabilities for the TokenBucketLimiter product:
1. `monitoring.usage_stats` — per-key usage statistics (total/success/rejected/peak_per_sec).
2. `security.rate_policy` — automatic blocking of keys after consecutive rejections.

## Files to change
- `src/ratelimit/stats.py` — `UsageStats` collector.
- `src/ratelimit/policy.py` — `RatePolicy` class (block_threshold, block_duration, blocked_until).
- `src/ratelimit/limiter.py` — stats tracking, `get_stats()`, and optional `RatePolicy` integration; `RatePolicy` lives in policy.py.
- `src/ratelimit/__init__.py` — export `UsageStats`.
- `docs/spec/monitoring/usage_stats.md` — normative spec for usage_stats.
- `docs/spec/security/rate_policy.md` — normative spec for rate_policy.

## Tests to add
- Stats: total == success + rejected invariant; peak_per_sec counting; unknown-key zeros.
- Policy: block after threshold, block expiry, consecutive-counter reset on success, invalid params.
- Integration: stats reflect both token-rejections and block-rejections; invariant holds with policy; block expiry allows consumption again.

## Out of scope
- No Change package, routing.yaml, coverage.yaml, FSM, or Decision files.
- No git push.

## Review notes
Fixed the failing review step. The limiter previously double-recorded every `consume` (a placeholder `record(success=False)` plus the real record), which made `total` twice the real count. It also recorded stats before checking the policy block, so blocked consumes were not counted. Now: blocked consumes record a rejection and return early; token successes increment the policy counter reset; token rejections increment the consecutive counter and may trigger a block. `blocked_until` is only present in stats while the block is active.
