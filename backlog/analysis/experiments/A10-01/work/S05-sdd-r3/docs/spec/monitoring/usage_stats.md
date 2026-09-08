# monitoring.usage_stats

## REQ-US-01 Statistics tracking
For every key the limiter MUST track the total number of `consume` calls, the number of successful calls, and the number of rejected calls (rejections caused by insufficient tokens OR by a policy block).

## REQ-US-02 Peak load
The limiter MUST track the peak load for each key, defined as the maximum number of `consume` calls observed within any single wall-clock second.

## REQ-US-03 get_stats
`get_stats(key)` MUST return a dict with at least the keys `total`, `success`, `rejected`, and `peak_per_sec`. For an unknown key all values MUST be zero.

## REQ-US-04 Stats consistency
The invariant `total == success + rejected` MUST hold after every `consume` call.
