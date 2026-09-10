# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock). While a key is under an active penalty lock, is_blocked(key) MUST return True.

## REQ-RL-05 penalty_seconds parameter
TokenBucketLimiter MUST accept an optional penalty_seconds parameter with a default of 0.0. Existing initializations without penalty_seconds MUST preserve prior behavior exactly.

## REQ-RL-06 blocked-state transition
WHEN penalty_seconds > 0 and a consume(key, tokens) call fails due to insufficient tokens, THE SYSTEM SHALL transition the key into a blocked state lasting penalty_seconds.

## REQ-RL-07 immediate block during penalty
WHILE a key is under an active penalty lock, THE SYSTEM SHALL return False from consume(key, tokens) immediately, even if tokens have accumulated during the penalty window.

## REQ-RL-08 auto-lift after penalty
WHEN penalty_seconds has fully elapsed for a blocked key, THE SYSTEM SHALL lift the block on the next consume call for that key and resume normal token-deduction logic.
