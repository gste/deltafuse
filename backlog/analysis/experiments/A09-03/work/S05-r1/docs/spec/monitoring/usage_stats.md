# monitoring.usage_stats

## REQ-US-01 Per-key counters
The Rate Limiter MUST track, per key, the total number of `consume` calls, the number of successful calls, and the number of rejected calls. A rejection is any `consume` call that returns `False`, whether caused by token shortage or by a policy-based block.

## REQ-US-02 Peak load
The Rate Limiter MUST track peak load per key, defined as the maximum number of `consume` calls observed within any single one-second window.

## REQ-US-03 get_stats
`get_stats(key)` MUST return a dictionary containing the tracked values from REQ-US-01 and REQ-US-02 for the given key. The dictionary MUST include keys for total calls, successful calls, rejected calls, and peak load.

## REQ-US-04 Rejection accounting
Stats MUST correctly reflect rejections caused by both token shortage and policy-based blocking without double-counting a single `consume` call.
