from ratelimit.limiter import TokenBucketLimiter
from ratelimit.policy import default_policy, evaluate


def test_default_policy_shape():
    policy = default_policy()
    assert policy == {'name': 'rate_policy', 'reject_threshold': 50, 'block_duration': 300.0}


def test_default_policy_custom():
    policy = default_policy(reject_threshold=10, block_duration=60.0)
    assert policy['reject_threshold'] == 10
    assert policy['block_duration'] == 60.0


def test_evaluate_threshold():
    assert evaluate({'rejected': 50}, 50) is True
    assert evaluate({'rejected': 49}, 50) is False
