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
        self._blocked_until: dict[str, float] = {}

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        self._buckets[key] = (tokens, now)
        return self._buckets[key]

    def consume(self, key: str, tokens: float) -> bool:
        if self.penalty_seconds > 0 and key in self._blocked_until:
            if time.monotonic() < self._blocked_until[key]:
                return False
            self._blocked_until.pop(key, None)
        current, ts = self._refill(key)
        if current >= tokens:
            self._buckets[key] = (current - tokens, ts)
            return True
        if self.penalty_seconds > 0:
            self._blocked_until[key] = time.monotonic() + self.penalty_seconds
        return False

    def is_blocked(self, key: str) -> bool:
        if self.penalty_seconds <= 0:
            return False
        end = self._blocked_until.get(key)
        if end is None:
            return False
        if time.monotonic() >= end:
            self._blocked_until.pop(key, None)
            return False
        return True