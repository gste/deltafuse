import time

from ratelimit.limiter import TokenBucketLimiter


def test_seed_consume_still_works():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    assert limiter.consume("user1", 5) is True
    assert limiter.consume("user1", 1) is False
    assert limiter.is_blocked("user1") is False


def test_stats_unknown_key_is_zero():
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)
    stats = limiter.get_stats("never-seen")
    assert stats["total_calls"] == 0
    assert stats["successful_calls"] == 0
    assert stats["rejected_calls"] == 0
    assert stats["token_rejects"] == 0
    assert stats["policy_rejects"] == 0
    assert stats["peak_rate"] == 0
    assert not stats.get("blocked_until")
    assert limiter.consume("other", 1) is True
    again = limiter.get_stats("never-seen")
    assert again["total_calls"] == 0


def test_stats_split_token_and_policy_rejects():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, reject_threshold=2, block_seconds=10.0
    )
    assert limiter.consume("k", 1) is True
    assert limiter.consume("k", 1) is False
    stats = limiter.get_stats("k")
    assert stats["token_rejects"] == 1
    assert stats["policy_rejects"] == 0
    assert limiter.consume("k", 1) is False
    assert limiter.is_blocked("k") is True
    assert limiter.consume("k", 1) is False
    stats = limiter.get_stats("k")
    assert stats["token_rejects"] >= 2
    assert stats["policy_rejects"] >= 1
    assert stats["rejected_calls"] == stats["token_rejects"] + stats["policy_rejects"]


def test_peak_rate_is_one_second_window():
    limiter = TokenBucketLimiter(
        capacity=100, refill_rate=100.0, reject_threshold=999, block_seconds=0.0
    )
    for _ in range(8):
        assert limiter.consume("burst", 1) is True
    peak = limiter.get_stats("burst")["peak_rate"]
    assert peak >= 8
    time.sleep(1.15)
    assert limiter.consume("burst", 1) is True
    later = limiter.get_stats("burst")
    assert later["peak_rate"] >= 8
    assert later["total_calls"] == 9


def test_policy_consecutive_lockout():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, reject_threshold=3, block_seconds=0.25
    )
    assert limiter.consume("k", 1) is True
    assert limiter.consume("k", 1) is False
    assert limiter.consume("k", 1) is False
    assert limiter.is_blocked("k") is False
    assert limiter.consume("k", 1) is False
    assert limiter.is_blocked("k") is True
    time.sleep(0.12)
    assert limiter.consume("k", 1) is False
    assert limiter.is_blocked("k") is True
    time.sleep(0.2)
    assert limiter.is_blocked("k") is False


def test_success_resets_consecutive_streak():
    limiter = TokenBucketLimiter(
        capacity=5, refill_rate=0.0, reject_threshold=3, block_seconds=30.0
    )
    assert limiter.consume("k", 1) is True
    assert limiter.consume("k", 5) is False
    assert limiter.consume("k", 1) is True
    assert limiter.consume("k", 5) is False
    assert limiter.consume("k", 5) is False
    assert limiter.is_blocked("k") is False


def test_blocked_consume_does_not_debit():
    limiter = TokenBucketLimiter(
        capacity=2, refill_rate=0.0, reject_threshold=1, block_seconds=0.2
    )
    assert limiter.consume("k", 1) is True
    assert limiter.consume("k", 2) is False
    assert limiter.is_blocked("k") is True
    time.sleep(0.25)
    assert limiter.is_blocked("k") is False
    assert limiter.consume("k", 1) is True


def test_keys_isolated_stats_and_policy():
    limiter = TokenBucketLimiter(
        capacity=1, refill_rate=0.0, reject_threshold=1, block_seconds=30.0
    )
    assert limiter.consume("a", 1) is True
    assert limiter.consume("a", 1) is False
    assert limiter.is_blocked("a") is True
    assert limiter.is_blocked("b") is False
    assert limiter.consume("b", 1) is True
    assert limiter.get_stats("b")["successful_calls"] == 1
    assert limiter.get_stats("a")["successful_calls"] == 1
    assert limiter.get_stats("b")["policy_rejects"] == 0
