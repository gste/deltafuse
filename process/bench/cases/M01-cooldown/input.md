# User request: small change to an existing capability

In the Rate Limiter service (`security.ratelimit`) add a temporary key lock when a consume attempt exceeds the limit (cool-down penalty).

Requirements:

1. Add an optional `penalty_seconds` parameter (default `0.0`) when constructing `TokenBucketLimiter`.
2. If `penalty_seconds > 0`:
   - On a failed `consume` (not enough tokens), the key MUST enter a blocked state for `penalty_seconds`.
   - Further `consume` calls for that key during the penalty MUST return `False` immediately, even if tokens have refilled.
3. After `penalty_seconds` the block MUST lift on the next request, and normal debit logic resumes.
4. `is_blocked(key)` MUST return `True` while the key is under penalty, and `False` otherwise.
5. Do not break backward compatibility: callers that omit `penalty_seconds` MUST behave as before.
