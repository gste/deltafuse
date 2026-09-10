from __future__ import annotations
import time

from .stats import UsageStats
from .policy import RatePolicy


class TokenBucketLimiter:
    def __init__(self, capacity: float, refill_rate: float) -> None:
        if capacity <= 0 or refill_rate < 0:
            raise ValueError('invalid limiter parameters')
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._buckets: dict[str, tuple[float, float]] = {}
        self._stats = UsageStats()
        self._rejections: dict[str, int] = {}
        self._policy = None

    def attach_policy(self, policy) -> None:
        self._policy = policy

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        self._buckets[key] = (tokens, now)
        return self._buckets[key]

    def consume(self, key: str, tokens: float) -> bool:
        if self._policy is not None and self._policy.is_blocked(key):
            self._stats.record(key, success=False)
            return False

        current, ts = self._refill(key)
        if current >= tokens:
            self._buckets[key] = (current - tokens, ts)
            self._stats.record(key, success=True)
            if self._policy is not None:
                self._policy.reset_counter(key)
            return True

        self._stats.record(key, success=False)
        if self._policy is not None:
            count = self._rejections.get(key, 0) + 1
            self._rejections[key] = count
            self._policy.note_rejection(key, count)
        return False

    def is_blocked(self, key: str) -> bool:
        if self._policy is not None:
            return self._policy.is_blocked(key)
        return False

    def get_stats(self, key: str) -> dict:
        stats = self._stats.snapshot(key)
        if self._policy is not None:
            blocked_until = self._policy.blocked_until(key)
            if blocked_until is not None:
                stats['blocked_until'] = blocked_until
        return stats


class RatePolicy:
    def __init__(self, block_threshold: int = 50, block_duration: float = 300.0) -> None:
        if block_threshold <= 0:
            raise ValueError('block_threshold must be > 0')
        if block_duration < 0:
            raise ValueError('block_duration must be >= 0')
        self.block_threshold = block_threshold
        self.block_duration = float(block_duration)
        self._blocked_until: dict[str, float] = {}
        self._counters: dict[str, int] = {}

    def note_rejection(self, key: str, count: int) -> None:
        if count >= self.block_threshold:
            self._blocked_until[key] = time.monotonic() + self.block_duration

    def is_blocked(self, key: str) -> bool:
        self._clear_expired(key)
        return key in self._blocked_until

    def blocked_until(self, key: str):
        self._clear_expired(key)
        return self._blocked_until.get(key)

    def reset_counter(self, key: str) -> None:
        self._counters[key] = 0

    def _clear_expired(self, key: str) -> None:
        until = self._blocked_until.get(key)
        if until is not None and time.monotonic() >= until:
            del self._blocked_until[key]
            self._counters[key] = 0
