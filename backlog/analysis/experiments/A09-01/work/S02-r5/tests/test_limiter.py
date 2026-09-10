from ratelimit.limiter import TokenBucketLimiter


def test_consume_and_reject():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_penalty_blocks_after_failed_consume():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=100.0, penalty_seconds=10.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    assert limiter.consume('u', 1) is False
