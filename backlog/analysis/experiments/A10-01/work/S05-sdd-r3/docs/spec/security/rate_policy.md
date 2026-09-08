# security.rate_policy

## REQ-RP-01 Block threshold
`RatePolicy` MUST accept a `block_threshold` (default 50) and a `block_duration` (default 300 seconds).

## REQ-RP-02 Automatic blocking
When the number of consecutive rejected `consume` calls for a key reaches `block_threshold`, the key MUST be blocked for `block_duration` seconds.

## REQ-RP-03 Blocked behavior
A blocked key MUST return `False` from `consume` without deducting tokens, and `is_blocked(key)` MUST return `True` while blocked.

## REQ-RP-04 blocked_until in stats
While a key is blocked, `get_stats(key)` MUST include a `blocked_until` timestamp. Once the block has expired, `blocked_until` MUST be absent (or null).

## REQ-RP-05 Consecutive counter reset
A successful `consume` MUST reset the consecutive-rejection counter. A rejection due to insufficient tokens MUST increment it; a rejection due to an active block MUST NOT increment it further.
