# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 get_balance
get_balance(key) MUST return the current non-negative integer token count available for the next consume call without deducting tokens or creating any side effecting deduction.

## REQ-RL-06 get_balance unknown keys
For an unknown key, get_balance(key) MUST return the initial capacity after normal key initialization.
