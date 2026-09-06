import time

from ratelimit.limiter import TokenBucketLimiter


def test_consume_and_reject():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_fractional_refill_accumulates():
    limiter = TokenBucketLimiter(capacity=10, refill_rate=0.5)

    # Unknown keys start at full capacity: first consume(capacity) MUST be True.
    assert limiter.consume('u', 10) is True

    # After ~1s only ~0.5 tokens accrue; cannot consume 1 more token.
    time.sleep(1)
    assert limiter.consume('u', 1) is False

    # After ~2s total ~1.0 tokens accrue; can consume 1 token.
    time.sleep(1)
    assert limiter.consume('u', 1) is True
