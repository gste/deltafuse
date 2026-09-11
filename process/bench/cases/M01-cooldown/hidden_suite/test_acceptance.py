import time

from ratelimit.limiter import TokenBucketLimiter


def test_backward_compatibility():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=1.0)
    assert limiter.consume("user1", 5) is True
    assert limiter.consume("user1", 1) is False
    assert limiter.is_blocked("user1") is False


def test_penalty_lockout_and_expiration():
    limiter = TokenBucketLimiter(capacity=2, refill_rate=10.0, penalty_seconds=0.2)
    assert limiter.consume("user2", 2) is True
    assert limiter.consume("user2", 1) is False
    assert limiter.is_blocked("user2") is True
    time.sleep(0.1)
    assert limiter.consume("user2", 1) is False
    assert limiter.is_blocked("user2") is True
    time.sleep(0.15)
    assert limiter.is_blocked("user2") is False
    assert limiter.consume("user2", 1) is True


def test_keys_isolated():
    limiter = TokenBucketLimiter(capacity=1, refill_rate=0.0, penalty_seconds=30.0)
    assert limiter.consume("a", 1) is True
    assert limiter.consume("a", 1) is False
    assert limiter.is_blocked("a") is True
    assert limiter.is_blocked("b") is False
    assert limiter.consume("b", 1) is True
