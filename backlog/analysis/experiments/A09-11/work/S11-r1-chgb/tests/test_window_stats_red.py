from ratelimit.limiter import TokenBucketLimiter


def test_get_window_stats_unknown_key_returns_zero_counters_and_full_capacity():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    stats = limiter.get_window_stats('unknown')
    assert stats == {'accepted': 0, 'rejected': 0, 'remaining_tokens': 5}


def test_get_window_stats_known_key_reflects_counters_and_read_only():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 3) is True
    before = limiter.get_window_stats('u')
    assert limiter.get_window_stats('u') == before
    assert before == {'accepted': 3, 'rejected': 0, 'remaining_tokens': 2}


def test_get_window_stats_does_not_consume_tokens():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    limiter.get_window_stats('u')
    assert limiter.get_window_stats('u') == {'accepted': 0, 'rejected': 0, 'remaining_tokens': 5}
