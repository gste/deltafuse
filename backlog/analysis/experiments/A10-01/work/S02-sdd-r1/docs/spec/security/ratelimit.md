# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Penalty lock
When initialized with penalty_seconds > 0, a failed consume (insufficient tokens) MUST place the key under a lock for penalty_seconds. While locked, any consume(key, tokens) call MUST return False immediately regardless of accumulated tokens. The lock MUST be released automatically after penalty_seconds elapse, at which point normal consume logic resumes. is_blocked(key) MUST return True while the key is locked and False otherwise. When penalty_seconds == 0 (default), no lock is ever applied and is_blocked always returns False.
