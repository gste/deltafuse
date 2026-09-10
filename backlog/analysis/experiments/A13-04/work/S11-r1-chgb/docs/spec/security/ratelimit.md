# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Window statistics
WHEN statistics are sampled for a key via get_window_stats(key) THE SYSTEM SHALL return a dict with fields accepted, rejected, and remaining_tokens for that key.

## REQ-RL-06 Window counter reset
WHEN the token-refill logic resets the window THE SYSTEM SHALL reset the accepted and rejected counters for the same window.

## REQ-RL-07 Non-consuming read
WHEN get_window_stats(key) is called THE SYSTEM SHALL NOT deduct tokens or change any limits.

## REQ-RL-08 Unknown key statistics
WHEN get_window_stats(key) is called for an unknown key THE SYSTEM SHALL return zero accepted and rejected counters and a remaining_tokens equal to full capacity.
