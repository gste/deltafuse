# security.rate_policy

## REQ-RP-01 Block-on-threshold policy
TokenBucketLimiter MAY accept a `reject_threshold` parameter (default 50). When the number of consecutive rejected `consume` calls for a key reaches this threshold, the limiter MUST block the key.

## REQ-RP-02 Block duration
When a key is blocked, `consume(key)` MUST return False without deducting tokens and `is_blocked(key)` MUST return True until `blocked_until`. The default block duration is 300 seconds.

## REQ-RP-03 blocked_until in stats
`get_stats(key)` MUST include `blocked_until` (a monotonic timestamp or None). While blocked, `blocked_until` MUST be set to the timestamp at which the block expires.

## REQ-RP-04 Consecutive reset on success
A successful `consume` call MUST reset the consecutive-reject counter so that the block threshold is measured in consecutive rejections, not total rejections.

## REQ-RP-05 Block accounting
Rejections caused by a policy block MUST be counted in the `rejected` statistic of `get_stats(key)`.
