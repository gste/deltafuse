## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Penalty cooldown
When initialized without penalty_seconds (default 0.0), is_blocked(key) MUST always return False. When initialized with penalty_seconds > 0, a failed consume(key) MUST place key into a blocked state for penalty_seconds. During the blocked state, consume(key) MUST return False immediately regardless of accumulated tokens. After penalty_seconds elapses, the block MUST clear automatically on the next consume call and normal token logic MUST resume.
