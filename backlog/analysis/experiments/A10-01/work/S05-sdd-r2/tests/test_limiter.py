from ratelimit.limiter import TokenBucketLimiter


def test_consume_and_reject():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_stats_counts_total_success_rejected():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 2) is True
    assert limiter.consume('u', 2) is True
    assert limiter.consume('u', 1) is False
    stats = limiter.get_stats('u')
    assert stats['total'] == 3
    assert stats['success'] == 2
    assert stats['rejected'] == 1


def test_stats_unknown_key_is_zeros():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    stats = limiter.get_stats('missing')
    assert stats['total'] == 0
    assert stats['success'] == 0
    assert stats['rejected'] == 0
    assert stats['peak_per_second'] == 0
    assert stats['blocked_until'] is None


def test_peak_per_second_reflects_window():
    limiter = TokenBucketLimiter(capacity=100, refill_rate=0.0)
    for _ in range(4):
        limiter.consume('u', 1)
    assert limiter.get_stats('u')['peak_per_second'] == 4


def test_policy_blocks_at_threshold():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, rejection_threshold=5, block_duration=300.0
    )
    assert limiter.consume('u', 1) is True
    for _ in range(4):
        assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    assert limiter.get_stats('u')['blocked_until'] is not None


def test_blocked_consume_no_deduction_and_no_counter_reset():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, rejection_threshold=5, block_duration=300.0
    )
    assert limiter.consume('u', 1) is True
    for _ in range(5):
        assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    stats = limiter.get_stats('u')
    assert stats['rejected'] == 5
    assert limiter.consume('u', 1) is False
    assert limiter.get_stats('u')['rejected'] == 6


def test_block_expires_and_resumes():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, rejection_threshold=5, block_duration=0.05
    )
    assert limiter.consume('u', 1) is True
    for _ in range(5):
        assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    import time

    time.sleep(0.06)
    assert limiter.is_blocked('u') is False
    assert limiter.consume('u', 1) is True


def test_blocked_rejections_counted_in_stats():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, rejection_threshold=3, block_duration=300.0
    )
    assert limiter.consume('u', 1) is True
    for _ in range(3):
        assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    limiter.consume('u', 1)  # still blocked, still rejected
    stats = limiter.get_stats('u')
    assert stats['rejected'] == 4
    assert stats['total'] == 5
    assert stats['success'] == 1
