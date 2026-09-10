# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Read-only balance accessor
get_balance(key) MUST return the current available token count for key as a non-negative integer without deducting tokens or creating any deduction side effect.

## REQ-RL-06 Read-only guarantee
get_balance(key) MUST NOT modify token accounting, refill state, or capacity for key or any other key.
