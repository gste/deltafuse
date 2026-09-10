from ratelimit.limiter import TokenBucketLimiter


def test_consume_and_reject():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_penalty_seconds_default_zero():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0, penalty_seconds=0.0)
    assert limiter.is_blocked('u') is False


def test_penalty_lock_blocks_and_is_blocked():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0, penalty_seconds=60.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    assert limiter.consume('u', 1) is False


def test_penalty_lock_blocks_then_clears():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=1.0, penalty_seconds=60.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False
