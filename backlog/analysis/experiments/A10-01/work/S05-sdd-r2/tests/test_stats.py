from ratelimit.limiter import TokenBucketLimiter
from ratelimit.stats import summarize_stats


def test_summarize_stats_defaults():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    raw = limiter.get_stats('u')
    summary = summarize_stats(raw)
    assert summary['total'] == 0
    assert summary['success'] == 0
    assert summary['rejected'] == 0
    assert summary['peak_per_second'] == 0
    assert summary['blocked_until'] is None


def test_summarize_stats_reflects_counts():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    limiter.consume('u', 2)
    limiter.consume('u', 2)
    raw = limiter.get_stats('u')
    summary = summarize_stats(raw)
    assert summary['total'] == 2
    assert summary['success'] == 2
    assert summary['rejected'] == 0
