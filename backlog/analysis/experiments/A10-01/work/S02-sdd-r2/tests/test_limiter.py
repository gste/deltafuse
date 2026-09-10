import time

from ratelimit.limiter import TokenBucketLimiter


def test_consume_and_reject():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_baseline_no_penalty_is_never_blocked():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_failed_consume_enters_blocked_state():
    limiter = TokenBucketLimiter(
        capacity=5, refill_rate=0.0, penalty_seconds=10.0
    )
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True


def test_consumes_return_false_while_blocked_even_with_tokens():
    limiter = TokenBucketLimiter(
        capacity=5, refill_rate=100.0, penalty_seconds=10.0
    )
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    # Even though refill_rate is high, blocked calls must reject immediately.
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True


def test_block_clears_after_penalty_and_normal_logic_resumes():
    limiter = TokenBucketLimiter(
        capacity=5, refill_rate=0.0, penalty_seconds=0.2
    )
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True

    time.sleep(0.25)

    assert limiter.is_blocked('u') is False
    # After penalty, normal consume logic resumes (tokens still zero here).
    assert limiter.consume('u', 1) is False
    # A fresh key can still consume normally.
    assert limiter.consume('v', 5) is True
