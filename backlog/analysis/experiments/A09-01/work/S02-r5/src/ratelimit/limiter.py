from __future__ import annotations
import time


class TokenBucketLimiter:
    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        penalty_seconds: float = 0.0,
    ) -> None:
        if capacity <= 0 or refill_rate < 0:
            raise ValueError('invalid limiter parameters')
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.penalty_seconds = float(penalty_seconds)
        self._buckets: dict[str, tuple[float, float]] = {}
        self._blocked: dict[str, float] = {}

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        self._buckets[key] = (tokens, now)
        return self._buckets[key]

    def _penalty_expired(self, key: str) -> bool:
        if self.penalty_seconds <= 0:
            return True
        expired = time.monotonic() - self._blocked[key] >= self.penalty_seconds
        if expired:
            del self._blocked[key]
        return expired

    def consume(self, key: str, tokens: float) -> bool:
        if key in self._blocked and not self._penalty_expired(key):
            return False
        current, ts = self._refill(key)
        if current >= tokens:
            self._buckets[key] = (current - tokens, ts)
            return True
        if self.penalty_seconds > 0:
            self._blocked[key] = time.monotonic()
        return False

    def is_blocked(self, key: str) -> bool:
        if key not in self._blocked:
            return False
        if self._penalty_expired(key):
            return False
        return True