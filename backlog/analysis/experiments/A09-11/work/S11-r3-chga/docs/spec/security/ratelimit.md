# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

When the key does not have enough tokens, consume MUST grant up to `burst_allowance` extra tokens once and retry the attempt within the same call. On the retry, consume MUST return True and deduct the requested tokens if the granted tokens are sufficient, otherwise return False without deduction. This retry MUST occur at most once per consume call.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-06 burst_allowance
TokenBucketLimiter MUST accept an optional `burst_allowance` parameter defaulting to 0. When `burst_allowance` is 0, consume MUST not grant extra tokens and behavior MUST be unchanged from the baseline single-attempt semantics.
