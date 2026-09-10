import time

from ratelimit.limiter import TokenBucketLimiter


def test_stats_reflect_token_and_policy_rejections():
    limiter = TokenBucketLimiter(
        capacity=2, refill_rate=0.0, reject_threshold=3, block_duration=10.0
    )
    # Two successful consumes drain the bucket.
    assert limiter.consume('u', 1) is True
    assert limiter.consume('u', 1) is True
    # Two token-insufficient rejections (not yet blocked).
    assert limiter.consume('u', 1) is False
    assert limiter.consume('u', 1) is False
    # Third consecutive rejection trips the policy block.
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    # Further consumes are policy-blocked rejections.
    assert limiter.consume('u', 1) is False
    assert limiter.consume('u', 1) is False

    stats = limiter.get_stats('u')
    assert stats['total'] == 7
    assert stats['success'] == 2
    assert stats['rejected'] == 5
    assert stats['blocked_until'] is not None
    assert stats['peak_per_second'] >= 1


def test_blocked_rejections_counted_but_success_resets():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, reject_threshold=2, block_duration=0.05
    )
    assert limiter.consume('u', 1) is True
    assert limiter.consume('u', 1) is False
    assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    # Blocked rejections accumulate.
    assert limiter.consume('u', 1) is False
    assert limiter.get_stats('u')['rejected'] == 3
    # Once the block expires, a successful consume resets the counter.
    time.sleep(0.06)
    assert limiter.is_blocked('u') is False
    assert limiter.consume('u', 1) is True
    assert limiter.get_stats('u')['success'] == 2
