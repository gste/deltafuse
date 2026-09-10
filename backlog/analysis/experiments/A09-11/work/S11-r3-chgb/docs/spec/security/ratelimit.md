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
get_window_stats(key) MUST return a dict with exactly the fields `accepted`,
`rejected`, and `remaining_tokens` for the requested key.

## REQ-RL-06 Window reset coupling
Window counters reported by get_window_stats MUST be reset together with the
token-replenishment reset path; there is no separate reset path for statistics.

## REQ-RL-07 No side effects
Calling get_window_stats MUST NOT consume tokens and MUST NOT change any limit,
capacity, or refill rate.

## REQ-RL-08 Unknown-key statistics
For an unknown key, get_window_stats MUST return `accepted=0`, `rejected=0`, and
`remaining_tokens` equal to the remainder assigned to a freshly seen key by
REQ-RL-03.
