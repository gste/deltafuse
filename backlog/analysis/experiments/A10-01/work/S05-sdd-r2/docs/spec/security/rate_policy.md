# security.rate_policy

## REQ-RP-01 Block on rejection threshold
When the number of consecutive rejected `consume` calls for a key reaches the configured rejection threshold, the limiter MUST automatically block the key.

## REQ-RP-02 Block duration
A blocked key MUST remain blocked for a configured duration (default 300 seconds). During this period `is_blocked(key)` MUST return True.

## REQ-RP-03 Blocked consume behavior
While a key is blocked, `consume` MUST return False without deducting tokens and MUST NOT reset the consecutive-rejection counter.

## REQ-RP-04 blocked_until in stats
`get_stats(key)` MUST include `blocked_until` (a monotonic timestamp) while the key is blocked, and MUST omit it (or set None) once the block has expired.

## REQ-RP-05 Block expiry
Once the current time exceeds `blocked_until`, the key MUST no longer be considered blocked and `consume` MUST resume normal token-bucket behavior.

## REQ-RP-06 Compatibility with stats
Policy-blocked rejections MUST be counted in the `rejected` counter of usage stats, consistent with token-insufficient rejections.
