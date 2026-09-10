# monitoring.usage_stats

## REQ-US-01 Per-key tracking
The `monitoring.usage_stats` capability MUST track, per key, the total number of `consume` calls, the number of successful calls, the number of rejected calls, and the peak load (maximum number of `consume` calls observed within any single one-second window).

## REQ-US-02 get_stats
`get_stats(key)` MUST return a dict containing the tracked values from REQ-US-01: `total`, `successful`, `rejected`, and `peak_calls_per_second`.

## REQ-US-03 Rejection accounting
`get_stats(key)` MUST count rejections caused by both token shortage and policy-based blocking under `rejected`. A policy-blocked key MUST additionally expose a `blocked_until` marker in its stats.

## REQ-US-04 Peak load resolution
Peak load is measured as the maximum number of `consume` calls observed within any single one-second fixed bucket, using the limiter's monotonic clock.
