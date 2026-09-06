# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return `False` for the baseline limiter (no penalty lock).
When `penalty_seconds > 0`, `is_blocked(key)` MUST return `True` while the key is
under penalty and `False` otherwise.

## REQ-RL-05 Cooldown penalty
When `penalty_seconds > 0`, a failed `consume` (insufficient tokens) MUST place
the key into a blocked state lasting `penalty_seconds`. While blocked, every
`consume` call for that key MUST return `False` immediately, even if tokens have
accumulated during the penalty window. After `penalty_seconds` elapses, the block
is lifted automatically on the next request and normal token-consumption logic
resumes.

## REQ-RL-06 is_blocked under penalty
is_blocked(key) MUST return `True` when the key is currently under penalty and
`False` otherwise.
