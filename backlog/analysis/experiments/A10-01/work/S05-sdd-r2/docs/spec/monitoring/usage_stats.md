# monitoring.usage_stats

## REQ-US-01 Stats tracking
TokenBucketLimiter MUST track per-key usage statistics: total number of `consume` calls, number of successful calls, and number of rejected calls.

## REQ-US-02 get_stats
`get_stats(key)` MUST return a dict with keys `total`, `success`, and `rejected` reflecting the counts since the key was first observed. For an unknown key, `get_stats` MUST return zeros.

## REQ-US-03 Peak load
`get_stats(key)` MUST include `peak_per_second`: the maximum number of `consume` calls observed within any single one-second window for that key.

## REQ-US-04 Rejection accounting
Both token-insufficient rejections and policy-blocked rejections MUST be counted in the `rejected` counter of stats.
