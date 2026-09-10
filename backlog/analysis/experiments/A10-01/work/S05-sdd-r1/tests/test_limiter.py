import time

from ratelimit.limiter import TokenBucketLimiter


def test_consume_and_reject():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 5) is True
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_unknown_key_stats_are_zeros():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    stats = limiter.get_stats('missing')
    assert stats == {
        'total': 0,
        'success': 0,
        'rejected': 0,
        'peak_per_second': 0,
        'blocked_until': None,
    }


def test_stats_counts_total_success_rejected():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume('u', 3) is True
    assert limiter.consume('u', 3) is False
    assert limiter.consume('u', 1) is True
    stats = limiter.get_stats('u')
    assert stats['total'] == 3
    assert stats['success'] == 2
    assert stats['rejected'] == 1


def test_peak_per_second_reflects_max_window():
    limiter = TokenBucketLimiter(capacity=100, refill_rate=0.0)
    for _ in range(4):
        limiter.consume('u', 1)
    # A later burst in a different one-second window should not exceed the peak.
    for _ in range(3):
        limiter.consume('u', 1)
    assert limiter.get_stats('u')['peak_per_second'] == 4


def test_policy_blocks_after_threshold():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, reject_threshold=3, block_duration=10.0
    )
    assert limiter.consume('u', 1) is True
    assert limiter.consume('u', 1) is False
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    assert limiter.consume('u', 1) is False
    assert limiter.get_stats('u')['blocked_until'] is not None


def test_blocked_consume_does_not_deduct_tokens():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, reject_threshold=2, block_duration=10.0
    )
    assert limiter.consume('u', 1) is True
    assert limiter.consume('u', 1) is False
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    stats = limiter.get_stats('u')
    # Only one successful consume happened; the rest were rejected/blocked.
    assert stats['success'] == 1
    assert stats['rejected'] == 2


def test_success_resets_consecutive_reject_counter():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, reject_threshold=3, block_duration=10.0
    )
    assert limiter.consume('u', 1) is True
    assert limiter.consume('u', 1) is False
    assert limiter.consume('u', 1) is False
    # Reset the counter with a successful consume (refill enough tokens).
    limiter._buckets['u'] = (limiter.capacity, time.monotonic())
    assert limiter.consume('u', 1) is True
    assert limiter.consume('u', 1) is False
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is False


def test_block_expires_and_is_uncblocked():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, reject_threshold=2, block_duration=0.05
    )
    assert limiter.consume('u', 1) is True
    assert limiter.consume('u', 1) is False
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    time.sleep(0.06)
    assert limiter.is_blocked('u') is False
