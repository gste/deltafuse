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
        # Each bucket stores (tokens, last_refill_timestamp, block_until).
        # block_until is 0.0 when the key is not blocked.
        self._buckets: dict[str, tuple[float, float, float]] = {}

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        stored = self._buckets.get(key)
        if stored is None:
            tokens, last = self.capacity, now
        else:
            tokens, last = stored[0], stored[1]
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        block_until = stored[2] if stored is not None else 0.0
        self._buckets[key] = (tokens, now, block_until)
        return tokens, now

    def consume(self, key: str, tokens: float) -> bool:
        now = time.monotonic()
        stored = self._buckets.get(key)
        if stored is not None and self.penalty_seconds > 0 and stored[2] > 0:
            if now < stored[2]:
                # Still within the penalty window: reject immediately.
                return False
            # Penalty window elapsed: clear the block and resume normal logic.
            self._buckets[key] = (stored[0], now, 0.0)

        current, ts = self._refill(key)
        if current >= tokens:
            block_until = 0.0
            if self.penalty_seconds > 0:
                block_until = now + self.penalty_seconds
            self._buckets[key] = (current - tokens, ts, block_until)
            return True
        return False

    def is_blocked(self, key: str) -> bool:
        if self.penalty_seconds <= 0:
            return False
        stored = self._buckets.get(key)
        if stored is None:
            return False
        now = time.monotonic()
        if stored[2] > 0 and now < stored[2]:
            return True
        return False
