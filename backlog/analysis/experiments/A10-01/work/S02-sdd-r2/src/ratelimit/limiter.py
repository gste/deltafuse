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

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        self._buckets[key] = (tokens, now)
        return self._buckets[key]

    def _is_expired(self, key: str, now: float) -> bool:
        entry = self._buckets.get(key)
        if entry is None:
            return True
        _, block_until = entry
        return block_until > 0.0 and now >= block_until

    def consume(self, key: str, tokens: float) -> bool:
        now = time.monotonic()
        if self.penalty_seconds > 0.0 and self._is_expired(key, now):
            # Penalty elapsed: clear the block and resume normal logic.
            self._buckets.pop(key, None)
        if self.penalty_seconds > 0.0:
            entry = self._buckets.get(key)
            if entry is not None and entry[1] > 0.0:
                # Still within the penalty window: reject immediately.
                return False
        current, ts = self._refill(key)
        if current >= tokens:
            self._buckets[key] = (current - tokens, ts)
            return True
        # Failed consume: impose penalty block if configured.
        if self.penalty_seconds > 0.0:
            self._buckets[key] = (current, now + self.penalty_seconds)
        return False

    def is_blocked(self, key: str) -> bool:
        if self.penalty_seconds <= 0.0:
            return False
        now = time.monotonic()
        entry = self._buckets.get(key)
        if entry is None:
            return False
        _, block_until = entry
        if block_until <= 0.0:
            return False
        return now < block_until
