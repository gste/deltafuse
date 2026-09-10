# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 burst_allowance
TokenBucketLimiter MAY initialize with an optional burst_allowance >= 0 (default 0). When burst_allowance is 0, consume/reject behavior is unchanged from REQ-RL-02.

## REQ-RL-06 burst retry
When consume(key, tokens) is rejected because the key lacks tokens, the key MAY still have burst_allowance tokens remaining. In that case the limiter grants `extra` tokens once and retries the consume attempt within the same invocation. The retry path MUST grant `extra` tokens exactly once per rejected call and MUST NOT repeat the grant on subsequent rejections.
