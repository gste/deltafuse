# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction. When the key is blocked by the rate policy, consume MUST return False without deduction (see REQ-RL-05).

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return True while a key is within its policy block window (now < blocked_until) and False otherwise.

## REQ-RL-05 Policy block contract
WHEN a key is blocked by the rate policy THE limiter SHALL return False from consume(key, tokens) without deducting tokens, and get_stats(key) SHALL report blocked_until as an ISO-8601 UTC timestamp or None when not blocked.

## REQ-RL-06 Policy activation
WHEN the number of consecutive rejected consumes for a key reaches the rejection threshold THE rate policy SHALL set blocked_until to now + block_duration_seconds for that key.

## REQ-RL-07 Usage stats
WHEN get_stats(key) is called THE limiter SHALL return a dict with keys total (int), successful (int), rejected (int), peak_load (float, max calls per second), and blocked_until (ISO-8601 UTC string or None).

## REQ-RL-08 Rejection accounting
WHEN a consume is rejected due to token shortage OR policy blocking THE rejected counter in get_stats(key) SHALL increment by one.
