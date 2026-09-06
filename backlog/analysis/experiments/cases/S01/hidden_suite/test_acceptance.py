import time
import pytest
from ratelimit.limiter import TokenBucketLimiter

def test_initialization_and_consumption():
    limiter = TokenBucketLimiter(capacity=10, refill_rate=2.0)
    assert limiter.consume("client1", 5) is True
    assert limiter.consume("client1", 5) is True
    assert limiter.consume("client1", 1) is False

def test_time_refill():
    limiter = TokenBucketLimiter(capacity=10, refill_rate=10.0)
    assert limiter.consume("client1", 10) is True
    assert limiter.consume("client1", 1) is False
    time.sleep(0.25)
    assert limiter.consume("client1", 2) is True

def test_invalid_parameters():
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=0, refill_rate=1.0)
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=10, refill_rate=-1.0)
    limiter = TokenBucketLimiter(capacity=5, refill_rate=1.0)
    with pytest.raises(ValueError):
        limiter.consume("client1", 0)
    with pytest.raises(ValueError):
        limiter.consume("client1", -2)
