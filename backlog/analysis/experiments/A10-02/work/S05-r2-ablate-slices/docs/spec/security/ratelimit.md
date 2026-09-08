# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 get_stats
get_stats(key) MUST return a dict with per-key counters: total_consumes, successful_consumes,
declined_consumes, peak_load, and blocked_until. declined_consumes counts both token-exhaustion
declines (REQ-RL-02) and policy-block declines (REQ-RL-07) without double-counting a single call.
blocked_until is an ISO-8601 timestamp string while the key is blocked, else null.

## REQ-RL-06 peak_load
peak_load MUST track the maximum number of consume calls observed within any single one-second
sliding window, updated on every consume call.

## REQ-RL-07 rate_policy auto-block
The limiter SHALL block a key for a configurable period once a consecutive-decline threshold is
exceeded; the consecutive-decline counter resets on any successful consume. Default threshold: 50
consecutive declines. Default block duration: 300 seconds.

## REQ-RL-08 blocked consume
While a key is blocked, consume(key, tokens) MUST return False without deducting tokens,
is_blocked(key) MUST return True, and blocked_until MUST be populated in stats; blocked_until
MUST be cleared (null) on expiry.
