# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction. When penalty_seconds > 0 and the key is blocked, consume MUST return False without deduction even if tokens are available.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Optional cooldown penalty
When constructed with penalty_seconds > 0, a failed consume (insufficient tokens) transitions the key into a blocked state lasting penalty_seconds. While blocked, every consume call for that key MUST return False immediately, even if tokens have accumulated during the penalty window.

## REQ-RL-06 Automatic block lift
After penalty_seconds elapses, the block lifts automatically on the next consume request and normal token-consumption logic resumes.

## REQ-RL-07 is_blocked under penalty
is_blocked(key) MUST return True while the key is under penalty and False otherwise.
