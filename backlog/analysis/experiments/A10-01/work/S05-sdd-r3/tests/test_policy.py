import time

from ratelimit.policy import RatePolicy


def test_policy_block_threshold_triggers_block():
    policy = RatePolicy(block_threshold=3, block_duration=300.0)
    assert policy.is_blocked('u') is False
    policy.note_rejection('u', 1)
    policy.note_rejection('u', 2)
    policy.note_rejection('u', 3)
    assert policy.is_blocked('u') is True
    assert policy.blocked_until('u') is not None


def test_policy_block_expiry():
    policy = RatePolicy(block_threshold=2, block_duration=0.0)
    policy.note_rejection('u', 2)
    assert policy.is_blocked('u') is True
    time.sleep(0.01)
    assert policy.is_blocked('u') is False


def test_policy_success_resets_counter():
    policy = RatePolicy(block_threshold=3, block_duration=300.0)
    policy.note_rejection('u', 1)
    policy.note_rejection('u', 2)
    policy.reset_counter('u')
    policy.note_rejection('u', 1)
    assert policy.is_blocked('u') is False


def test_policy_invalid_params():
    try:
        RatePolicy(block_threshold=0)
    except ValueError:
        pass
    else:
        raise AssertionError('expected ValueError')
