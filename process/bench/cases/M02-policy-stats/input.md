# User request: usage stats and a reject policy on the existing limiter

We already have an in-process token-bucket (`security.ratelimit`). This change must add **two** capabilities that work together. Do not treat this as a single-file tweak: add `src/ratelimit/stats.py` and `src/ratelimit/policy.py`, and keep `get_stats` on `TokenBucketLimiter` in `src/ratelimit/limiter.py`.

1. New capability `monitoring.usage_stats`
   For each key, `get_stats(key)` MUST return:
   - `total_calls`
   - `successful_calls`
   - `rejected_calls` (equals `token_rejects` + `policy_rejects`)
   - `token_rejects` — empty-bucket rejects
   - `policy_rejects` — rejects while the key is policy-blocked
   - `peak_rate` — highest number of `consume` calls in any rolling 1-second window
   - `blocked_until` — monotonic deadline, or 0 when not blocked
   An unknown key returns zeros for those fields and must not create usage state.

2. New capability `security.rate_policy`
   `TokenBucketLimiter` MUST accept `reject_threshold` (default 50) and `block_seconds` (default 300.0).
   After `reject_threshold` **consecutive** failed `consume` calls, block that key for `block_seconds`.
   While blocked:
   - `consume` returns `False` immediately
   - tokens MUST NOT be deducted
   - `is_blocked(key)` is `True`
   - stats record those calls as `policy_rejects` and expose `blocked_until`
   A successful consume resets the consecutive-failure streak. Non-consecutive failures must not trigger the block.
   After the block expires, normal debit resumes.

Both capabilities are in scope. Wire them: stats must see policy blocks, policy must see token rejects.

Out of scope for this change: sharing state across processes, Redis, HTTP, or any other network backend. That is a later Change. This one stays in-process.

Do not invent a Decision unless the request is actually ambiguous. Defaults above are the product decision.
