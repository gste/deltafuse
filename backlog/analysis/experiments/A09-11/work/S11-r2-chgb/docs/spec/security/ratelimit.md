# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Window statistics
get_window_stats(key) MUST return a dictionary with integer fields `accepted`, `rejected`, and `remaining_tokens` for the given key, without consuming tokens or changing limits.

## REQ-RL-06 Window counter reset
Window counters tracked for get_window_stats MUST be reset together with the token-replenishment logic of the limiter.

## REQ-RL-07 Unknown-key statistics
For an unknown key, get_window_stats MUST return zero `accepted` and `rejected` counters and a `remaining_tokens` equal to the current remainder per the key-initialization rules.
