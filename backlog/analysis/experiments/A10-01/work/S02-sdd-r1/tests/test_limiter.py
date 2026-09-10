import time

from ratelimit.limiter import TokenBucketLimiter


def test_consume_and_reject():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_penalty_lock_blocks_immediately():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0, penalty_seconds=10.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    # Still blocked even though refill_rate would add tokens.
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True


def test_penalty_auto_releases():
    limiter = TokenBucketLimiter(
        capacity=5, refill_rate=100.0, penalty_seconds=0.05
    )
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True

    time.sleep(0.06)
    assert limiter.is_blocked('u') is False
    # After lock expires, tokens have accumulated and consume succeeds.
    assert limiter.consume('u', 1) is True


def test_baseline_never_blocks():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False
