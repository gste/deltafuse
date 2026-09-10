# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction. Recording attempt history MUST NOT alter the accept/reject result or token accounting of consume (CR-007).

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Attempt history recording
Every call to consume(key, tokens) MUST record an event containing the key, the timestamp of the call, the requested token count, and the outcome (`accepted` when consume returns True, `rejected` when it returns False). Recording MUST NOT change the result or token accounting of consume (CR-002, CR-007).

## REQ-RL-06 get_history
get_history(key, n=10) MUST return the last `n` recorded events for `key`, newest first. `n` MUST be an integer `>= 1`; a value that is not an integer or is `< 1` MUST raise an exception. The default value of `n` is `10` (CR-003, CR-004, CR-005).

## REQ-RL-07 Per-key history isolation
History records for different keys MUST be isolated and never mixed (CR-006).
