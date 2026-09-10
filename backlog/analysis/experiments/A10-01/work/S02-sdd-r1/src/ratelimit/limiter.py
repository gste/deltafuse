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
        # key -> (tokens, last_refill_ts)
        self._buckets: dict[str, tuple[float, float]] = {}
        # key -> monotonic timestamp when the lock expires (0.0 if not locked)
        self._locks: dict[str, float] = {}

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        self._buckets[key] = (tokens, now)
        return self._buckets[key]

    def _is_locked(self, key: str, now: float) -> bool:
        expiry = self._locks.get(key, 0.0)
        if expiry and now < expiry:
            return True
        # Lock expired: clear it so normal logic resumes.
        if expiry:
            self._locks.pop(key, None)
        return False

    def consume(self, key: str, tokens: float) -> bool:
        now = time.monotonic()
        if self._is_locked(key, now):
            return False
        current, ts = self._refill(key)
        if current >= tokens:
            self._buckets[key] = (current - tokens, ts)
            return True
        # Failed consume: apply penalty lock when configured.
        if self.penalty_seconds > 0:
            self._locks[key] = now + self.penalty_seconds
        return False

    def is_blocked(self, key: str) -> bool:
        return self._is_locked(key, time.monotonic())
