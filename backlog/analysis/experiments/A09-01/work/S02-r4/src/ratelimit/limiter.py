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
        self._blocks: dict[str, float] = {}

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        self._buckets[key] = (tokens, now)
        return self._buckets[key]

    def _block_expired(self, key: str, now: float) -> bool:
        expiry = self._blocks.get(key)
        if expiry is None:
            return True
        if now >= expiry:
            del self._blocks[key]
            return True
        return False

    def consume(self, key: str, tokens: float) -> bool:
        now = time.monotonic()
        if not self._block_expired(key, now):
            return False
        current, ts = self._refill(key)
        if current >= tokens:
            self._buckets[key] = (current - tokens, ts)
            return True
        if self.penalty_seconds > 0:
            self._blocks[key] = now + self.penalty_seconds
        return False

    def is_blocked(self, key: str) -> bool:
        now = time.monotonic()
        if self._block_expired(key, now):
            return False
        return True