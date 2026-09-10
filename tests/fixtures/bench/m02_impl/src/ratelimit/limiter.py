from __future__ import annotations

import time

from ratelimit.policy import RatePolicy
from ratelimit.stats import UsageStats


class TokenBucketLimiter:
    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        reject_threshold: int = 50,
        block_seconds: float = 300.0,
    ) -> None:
        if capacity <= 0 or refill_rate < 0:
            raise ValueError("invalid limiter parameters")
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._buckets: dict[str, tuple[float, float]] = {}
        self._stats = UsageStats()
        self._policy = RatePolicy(reject_threshold, block_seconds)

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        self._buckets[key] = (tokens, now)
        return self._buckets[key]

    def consume(self, key: str, tokens: float) -> bool:
        now = time.monotonic()
        if self._policy.is_blocked(key, now):
            until = self._policy.blocked_until(key, now)
            self._stats.record(key, ok=False, reason="policy", blocked_until=until)
            return False
        current, ts = self._refill(key)
        if current >= tokens:
            self._buckets[key] = (current - tokens, ts)
            self._policy.note_success(key)
            self._stats.record(key, ok=True, reason=None, blocked_until=0.0)
            return True
        until = self._policy.note_token_reject(key, now)
        self._stats.record(key, ok=False, reason="token", blocked_until=until)
        return False

    def is_blocked(self, key: str) -> bool:
        return self._policy.is_blocked(key, time.monotonic())

    def get_stats(self, key: str) -> dict[str, float | int]:
        return self._stats.get_stats(key)
