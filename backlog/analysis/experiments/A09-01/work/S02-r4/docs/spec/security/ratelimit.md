# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0. It
MUST accept an optional `penalty_seconds` parameter with a default value of `0.0`.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Penalty lock
When `penalty_seconds > 0`, a failed `consume` (insufficient tokens) transitions
the key into a blocked state lasting `penalty_seconds`. While blocked, `consume`
for that key MUST return `False` immediately, even if tokens have accumulated.
The block auto-clears after the penalty window on the next request, restoring
normal spending logic. The block timer starts at the failed `consume` call.

## REQ-RL-06 is_blocked under penalty
`is_blocked(key)` MUST return `True` when the key is currently under penalty and
`False` otherwise.
