import time

from ratelimit.limiter import TokenBucketLimiter


def test_consume_and_reject():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_unknown_key_starts_at_full_capacity():
    limiter = TokenBucketLimiter(capacity=10, refill_rate=0.5)
    assert limiter.consume('new', 10) is True


def test_fractional_refill_accumulates():
    limiter = TokenBucketLimiter(capacity=10, refill_rate=0.5)
    assert limiter.consume('u', 10) is True
    time.sleep(1.0)
    assert limiter.consume('u', 1) is False
    time.sleep(1.0)
    assert limiter.consume('u', 1) is True
