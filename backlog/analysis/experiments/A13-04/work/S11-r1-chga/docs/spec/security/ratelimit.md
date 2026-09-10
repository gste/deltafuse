# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Optional burst_allowance
WHEN `burst_allowance` is not specified THE TokenBucketLimiter SHALL default it to 0 and preserve baseline consume semantics.

WHEN a consume is rejected for a key that still has unused `burst_allowance` tokens THE SYSTEM SHALL grant those extra tokens once and retry the consume within the same call.

WHEN a consume has been retried once via `burst_allowance` THE SYSTEM SHALL NOT grant additional burst tokens for that same consume call.
