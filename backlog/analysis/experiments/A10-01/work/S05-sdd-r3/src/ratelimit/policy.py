from __future__ import annotations
import time


class RatePolicy:
    """Blocks a key after a threshold of consecutive rejections."""

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
