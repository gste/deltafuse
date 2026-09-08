# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Penalty cooldown
When initialized without penalty_seconds (default 0.0), behavior is identical to the baseline. When initialized with penalty_seconds > 0:

- On a failed consume (insufficient tokens), the key MUST enter a blocked state lasting penalty_seconds.
- While blocked, every consume call for that key MUST return False immediately, even if tokens have since accumulated.
- After penalty_seconds elapses, the block MUST clear automatically on the next request, restoring normal consume logic.

## REQ-RL-06 is_blocked with penalty
is_blocked(key) MUST return True while the key is under a penalty block and False otherwise.
