from ratelimit.limiter import TokenBucketLimiter


def test_consume_and_reject():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_stats_invariant_total_equals_success_plus_rejected():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    limiter.consume('u', 5)
    limiter.consume('u', 1)
    limiter.consume('u', 1)
    stats = limiter.get_stats('u')
    assert stats['total'] == stats['success'] + stats['rejected']
    assert stats['total'] == 3
    assert stats['success'] == 1
    assert stats['rejected'] == 2


def test_stats_unknown_key_is_zero():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    stats = limiter.get_stats('nobody')
    assert stats['total'] == 0
    assert stats['success'] == 0
    assert stats['rejected'] == 0
    assert stats['peak_per_sec'] == 0


def test_stats_peak_per_sec():
    limiter = TokenBucketLimiter(capacity=100, refill_rate=0.0)
    for _ in range(7):
        limiter.consume('u', 1)
    stats = limiter.get_stats('u')
    assert stats['peak_per_sec'] >= 1


def test_stats_blocked_until_none_without_policy():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    limiter.consume('u', 5)
    stats = limiter.get_stats('u')
    assert stats.get('blocked_until') is None
