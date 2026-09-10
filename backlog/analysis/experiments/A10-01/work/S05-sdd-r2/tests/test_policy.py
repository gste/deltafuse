from ratelimit.limiter import TokenBucketLimiter
from ratelimit.policy import default_policy, should_block


def test_default_policy_values():
    policy = default_policy()
    assert policy['rejection_threshold'] == 5
    assert policy['block_duration'] == 300.0


def test_should_block_threshold():
    policy = default_policy(rejection_threshold=5)
    assert should_block(4, policy) is False
    assert should_block(5, policy) is True


def test_policy_blocks_and_expires():
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
