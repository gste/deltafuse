# User request: usage stats and a reject policy on the existing limiter

We already have an in-process token-bucket (`security.ratelimit`). This change must add **two** things that work together. Do not treat this as a single-file tweak.

1. New capability `monitoring.usage_stats`
   For each key, record how `consume` is used:
   - total calls
   - successes
   - rejections
   - peak load: the highest number of `consume` calls observed in any rolling 1-second window
   Expose `get_stats(key)` on the limiter. An unknown key returns zeros and must not create usage.
   Rejections caused by an empty bucket and rejections caused by a policy block MUST be stored as separate counters. Do not collapse them into one number.

2. New capability `security.rate_policy`
   After a configurable number of **consecutive** failed `consume` calls (default 50), block that key for a configurable duration (default 300 seconds).
   While blocked:
   - `consume` returns `False` immediately
   - tokens MUST NOT be deducted
   - `is_blocked(key)` is `True`
   Stats MUST still record those blocked calls as policy rejections, and include `blocked_until` (monotonic deadline, or 0 when not blocked).
   A successful consume resets the consecutive-failure streak. Non-consecutive failures must not trigger the block.
   After the block expires, normal debit resumes.

Both capabilities are in scope. Wire them: stats must see policy blocks, policy must see token rejects.

Out of scope for this change: sharing state across processes, Redis, HTTP, or any other network backend. That is a later Change. This one stays in-process.

Do not invent a Decision unless the request is actually ambiguous. Defaults above are the product decision.
