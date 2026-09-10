from ratelimit.limiter import TokenBucketLimiter
from ratelimit.stats import rejection_rate, summarize


def test_summarize_normalizes_stats():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    limiter.consume('u', 3)
    stats = limiter.get_stats('u')
    assert summarize(stats) == {
        'total': 1,
        'success': 1,
        'rejected': 0,
        'peak_per_second': 1,
        'blocked_until': None,
    }


def test_rejection_rate_zero_for_empty():
    assert rejection_rate({'total': 0, 'rejected': 0}) == 0.0


def test_rejection_rate_reflects_rejections():
    assert rejection_rate({'total': 4, 'rejected': 2}) == 0.5


def test_summarize_unknown_key():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert summarize(limiter.get_stats('missing')) == {
        'total': 0,
        'success': 0,
        'rejected': 0,
        'peak_per_second': 0,
        'blocked_until': None,
    }
