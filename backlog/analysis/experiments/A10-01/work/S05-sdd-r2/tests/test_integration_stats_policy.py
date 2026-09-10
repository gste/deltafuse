from ratelimit.limiter import TokenBucketLimiter
from ratelimit.stats import summarize_stats


def test_policy_blocked_rejections_reflected_in_stats():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, rejection_threshold=3, block_duration=300.0
    )
    assert limiter.consume('u', 1) is True
    for _ in range(3):
        assert limiter.consume('u', 1) is False
    assert limiter.is_blocked('u') is True
    # Extra blocked consumes remain rejected and do not reset the counter.
    assert limiter.consume('u', 1) is False
    summary = summarize_stats(limiter.get_stats('u'))
    assert summary['total'] == 5
    assert summary['success'] == 1
    assert summary['rejected'] == 4
    assert summary['blocked_until'] is not None
