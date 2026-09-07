# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Usage stats
The limiter MUST expose `get_stats(key)` returning a dictionary with at least: total `consume` count, successful count, denied count, and peak 1-second load (max calls observed within any single second). Denials caused by both token shortage and policy-based blocking MUST be counted as denials.

## REQ-RL-06 Rate policy auto-block
When a key accumulates a threshold of consecutive denied `consume` calls, the limiter MUST automatically block the key for a configurable period (default 300 s). A blocked key MUST return `False` from `consume` without deducting tokens, and its stats MUST include a `blocked_until` marker.

## REQ-RL-07 Consecutive-denial reset
A successful `consume` MUST reset the consecutive-denial counter so the auto-block threshold counts only consecutive denials.
