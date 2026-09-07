# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Consume event record
Every call to consume(key, tokens) MUST record an event containing the key, the moment in time the call was made, the requested token count, and the outcome (`accepted` when tokens were deducted, `rejected` otherwise).

## REQ-RL-06 get_history
get_history(key, n=10) MUST return the last `n` recorded events for the key, newest first.

## REQ-RL-07 n validation
The parameter `n` MUST be an integer >= 1; an exception MUST be raised for any other value.

## REQ-RL-08 n default
The default value of `n` in get_history MUST be 10.

## REQ-RL-09 Per-key isolation
Events recorded for different keys MUST not be mixed; get_history(key) MUST return only events for that key.

## REQ-RL-10 Semantic invariance
Enabling history MUST NOT change the semantics of consume: the same keys, the same limits, and the same accepted/rejected result MUST be produced as without history.
