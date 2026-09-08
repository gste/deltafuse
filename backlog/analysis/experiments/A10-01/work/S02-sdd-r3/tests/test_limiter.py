import time

from ratelimit.limiter import TokenBucketLimiter


def test_consume_and_reject():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_baseline_never_blocks():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False
    assert limiter.is_blocked('unknown') is False


def test_penalty_blocks_after_failed_consume():
    limiter = TokenBucketLimiter(
        capacity=5, refill_rate=0.0, penalty_seconds=1.0
    )
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True


def test_penalty_rejects_even_with_accumulated_tokens():
    # High refill rate would normally restore tokens, but the block must win.
    limiter = TokenBucketLimiter(
        capacity=5, refill_rate=1000.0, penalty_seconds=1.0
    )
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True


def test_penalty_clears_after_window():
    limiter = TokenBucketLimiter(
        capacity=5, refill_rate=0.0, penalty_seconds=0.2
    )
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    time.sleep(0.25)
    assert limiter.is_blocked('u') is False
    # Normal token logic resumes: bucket is empty, so this fails again.
    assert limiter.consume('u', 1) is False
    # But a fresh key can consume.
    assert limiter.consume('v', 1) is True
