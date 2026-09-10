from __future__ import annotations
import time

class TokenBucketLimiter:
    def __init__(self, capacity: float, refill_rate: float) -> None:
        if capacity <= 0 or refill_rate < 0:
            raise ValueError('invalid limiter parameters')
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._buckets: dict[str, tuple[float, float]] = {}

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        gained = (now - last) * self.refill_rate
        tokens = min(self.capacity, tokens + gained)
        self._buckets[key] = (tokens, now)
        return self._buckets[key]

    def consume(self, key: str, tokens: float) -> bool:
        current, ts = self._refill(key)
        if current >= tokens:
            self._buckets[key] = (current - tokens, ts)
            return True
        return False

    def is_blocked(self, key: str) -> bool:
        return False