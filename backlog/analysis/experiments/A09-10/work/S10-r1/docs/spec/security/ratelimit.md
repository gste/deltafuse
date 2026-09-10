# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Consume event recording
Every call to consume(key, tokens) MUST record an immutable event containing the key, the moment in time, the requested token count, and the outcome (accepted or rejected).

## REQ-RL-06 History retrieval
get_history(key, n=10) MUST return the last n events for the given key, newest first.

## REQ-RL-07 History argument validation
The parameter n MUST be an integer >= 1. An invalid n MUST raise an exception.

## REQ-RL-08 History isolation
History recording MUST NOT change the semantics of consume (REQ-RL-02/03). Records for different keys MUST NOT be mixed.
