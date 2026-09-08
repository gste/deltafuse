from __future__ import annotations
import time


class TokenBucketLimiter:
    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        rejection_threshold: int = 5,
        block_duration: float = 300.0,
    ) -> None:
        if capacity <= 0 or refill_rate < 0:
            raise ValueError('invalid limiter parameters')
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.rejection_threshold = int(rejection_threshold)
        self.block_duration = float(block_duration)
        self._buckets: dict[str, tuple[float, float]] = {}
        self._consecutive_rejections: dict[str, int] = {}
        self._blocked_until: dict[str, float] = {}
        self._stats: dict[str, dict] = {}
        self._last_consume_ts: dict[str, float] = {}
        self._consume_counts_in_window: dict[str, list[float]] = {}

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        self._buckets[key] = (tokens, now)
        return self._buckets[key]

    def _record_consume(self, key: str, success: bool) -> None:
        now = time.monotonic()
        stats = self._stats.setdefault(
            key, {'total': 0, 'success': 0, 'rejected': 0, 'peak_per_second': 0}
        )
        stats['total'] += 1
        if success:
            stats['success'] += 1
        else:
            stats['rejected'] += 1
        window_start = now - 1.0
        counts = self._consume_counts_in_window.setdefault(key, [])
        while counts and counts[0] < window_start:
            counts.pop(0)
        counts.append(now)
        stats['peak_per_second'] = max(stats['peak_per_second'], len(counts))

    def _update_block(self, key: str) -> None:
        now = time.monotonic()
        if key in self._blocked_until and now >= self._blocked_until[key]:
            del self._blocked_until[key]
            self._consecutive_rejections[key] = 0

    def consume(self, key: str, tokens: float) -> bool:
        self._update_block(key)
        if key in self._blocked_until:
            self._record_consume(key, success=False)
            return False
        current, ts = self._refill(key)
        if current >= tokens:
            self._buckets[key] = (current - tokens, ts)
            self._consecutive_rejections[key] = 0
            self._record_consume(key, success=True)
            return True
        self._consecutive_rejections[key] = (
            self._consecutive_rejections.get(key, 0) + 1
        )
        if self._consecutive_rejections[key] >= self.rejection_threshold:
            self._blocked_until[key] = time.monotonic() + self.block_duration
        self._record_consume(key, success=False)
        return False

    def is_blocked(self, key: str) -> bool:
        self._update_block(key)
        return key in self._blocked_until

    def get_stats(self, key: str) -> dict:
        self._update_block(key)
        stats = self._stats.get(
            key, {'total': 0, 'success': 0, 'rejected': 0, 'peak_per_second': 0}
        )
        result = dict(stats)
        result.setdefault('total', 0)
        result.setdefault('success', 0)
        result.setdefault('rejected', 0)
        result.setdefault('peak_per_second', 0)
        result['blocked_until'] = (
            self._blocked_until.get(key) if key in self._blocked_until else None
        )
        return result
