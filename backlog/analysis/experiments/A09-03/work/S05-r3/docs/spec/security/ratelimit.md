# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Rate policy auto-block
When the `security.rate_policy` policy determines a key has exceeded its rejection threshold, `consume(key, tokens)` MUST return False without deducting tokens for the duration of the block, and `is_blocked(key)` MUST return True until the block expires.

## REQ-RL-06 Rate policy default block period
The default rate-policy block period is 300 seconds and MUST be configurable.
