import time

from ratelimit.limiter import TokenBucketLimiter, RatePolicy


def test_stats_reflect_token_and_block_rejections():
    limiter = TokenBucketLimiter(capacity=1, refill_rate=0.0)
    policy = RatePolicy(block_threshold=2, block_duration=300.0)
    limiter.attach_policy(policy)

    assert limiter.consume('u', 1) is True  # success
    assert limiter.consume('u', 1) is False  # token rejection (counter=1)
    assert limiter.consume('u', 1) is False  # token rejection (counter=2 -> block)

    stats = limiter.get_stats('u')
    assert stats['total'] == 3
    assert stats['success'] == 1
    assert stats['rejected'] == 2
    assert stats['blocked_until'] is not None

    # blocked consumes count as rejected but not as token rejections
    assert limiter.consume('u', 1) is False
    stats = limiter.get_stats('u')
    assert stats['total'] == 4
    assert stats['rejected'] == 3
    assert stats['success'] == 1


def test_invariant_holds_with_policy():
    limiter = TokenBucketLimiter(capacity=1, refill_rate=0.0)
    policy = RatePolicy(block_threshold=2, block_duration=300.0)
    limiter.attach_policy(policy)

    for _ in range(6):
        limiter.consume('u', 1)
    stats = limiter.get_stats('u')
    assert stats['total'] == stats['success'] + stats['rejected']


def test_block_expiry_allows_consumption_again():
    limiter = TokenBucketLimiter(capacity=1, refill_rate=0.0)
    policy = RatePolicy(block_threshold=2, block_duration=0.0)
    limiter.attach_policy(policy)

    assert limiter.consume('u', 1) is True
    assert limiter.consume('u', 1) is False
    assert limiter.consume('u', 1) is False
    time.sleep(0.01)
    assert limiter.consume('u', 1) is True
    stats = limiter.get_stats('u')
    assert stats['success'] == 2
    assert limiter.get_stats('u')['blocked_until'] is None
