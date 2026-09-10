import time
import pytest
from ratelimit.limiter import TokenBucketLimiter

def test_fractional_refill_precision():
    # refill_rate = 0.5 token/sec. Capacity = 5.
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.5)
    assert limiter.consume("client", 5) is True
    assert limiter.consume("client", 1) is False
    
    # Wait 1.0s -> 0.5 tokens accumulated (not enough for 1 token)
    time.sleep(1.0)
    assert limiter.consume("client", 1) is False
    
    # Wait another 1.1s -> total elapsed 2.1s -> 1.05 tokens accumulated (enough for 1)
    time.sleep(1.1)
    assert limiter.consume("client", 1) is True
    assert limiter.consume("client", 1) is False

def test_no_spec_regression():
    limiter = TokenBucketLimiter(capacity=10, refill_rate=2.0)
    assert limiter.consume("c2", 10) is True
    time.sleep(0.5) # 1 token refilled
    assert limiter.consume("c2", 1) is True
