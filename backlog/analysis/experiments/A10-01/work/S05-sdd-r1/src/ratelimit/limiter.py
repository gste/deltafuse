from __future__ import annotations
import time


class TokenBucketLimiter:
    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        reject_threshold: int = 50,
        block_duration: float = 300.0,
    ) -> None:
        if capacity <= 0 or refill_rate < 0:
            raise ValueError('invalid limiter parameters')
        if reject_threshold <= 0:
            raise ValueError('invalid reject_threshold')
        if block_duration < 0:
            raise ValueError('invalid block_duration')
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.reject_threshold = int(reject_threshold)
        self.block_duration = float(block_duration)
        self._buckets: dict[str, tuple[float, float]] = {}
        self._rejects: dict[str, int] = {}
        self._stats: dict[str, dict] = {}
        self._blocks: dict[str, float] = {}
        self._second_counts: dict[str, dict[int, int]] = {}

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        self._buckets[key] = (tokens, now)
        return self._buckets[key]

    def _record_second(self, key: str, now: float) -> None:
        bucket = int(now)
        counts = self._second_counts.setdefault(key, {})
        counts[bucket] = counts.get(bucket, 0) + 1
        stats = self._stats.setdefault(
            key, {'total': 0, 'success': 0, 'rejected': 0, 'peak_per_second': 0}
        )
        if counts[bucket] > stats['peak_per_second']:
            stats['peak_per_second'] = counts[bucket]

    def consume(self, key: str, tokens: float) -> bool:
        now = time.monotonic()
        self._record_second(key, now)
        stats = self._stats.setdefault(
            key, {'total': 0, 'success': 0, 'rejected': 0, 'peak_per_second': 0}
        )
        stats['total'] += 1

        block_until = self._blocks.get(key)
        if block_until is not None and now < block_until:
            stats['rejected'] += 1
            return False

        if block_until is not None and now >= block_until:
            del self._blocks[key]

        current, ts = self._refill(key)
        if current >= tokens:
            self._buckets[key] = (current - tokens, ts)
            stats['success'] += 1
            self._rejects[key] = 0
            return True

        stats['rejected'] += 1
        self._rejects[key] = self._rejects.get(key, 0) + 1
        if self._rejects[key] >= self.reject_threshold:
            self._blocks[key] = now + self.block_duration
        return False

    def is_blocked(self, key: str) -> bool:
        now = time.monotonic()
        block_until = self._blocks.get(key)
        if block_until is not None and now >= block_until:
            del self._blocks[key]
            return False
        return block_until is not None

    def get_stats(self, key: str) -> dict:
        stats = self._stats.get(key)
        if stats is None:
            return {
                'total': 0,
                'success': 0,
                'rejected': 0,
                'peak_per_second': 0,
                'blocked_until': None,
            }
        result = dict(stats)
        result['blocked_until'] = self._blocks.get(key)
        return result


def is_blocked(key: str) -> bool:  # pragma: no cover - baseline compatibility shim
    return False
