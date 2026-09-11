from __future__ import annotations


class RatePolicy:
    def __init__(self, reject_threshold: int = 50, block_seconds: float = 300.0) -> None:
        if reject_threshold < 1 or block_seconds < 0:
            raise ValueError("invalid policy parameters")
        self.reject_threshold = int(reject_threshold)
        self.block_seconds = float(block_seconds)
        self._streak: dict[str, int] = {}
        self._until: dict[str, float] = {}

    def blocked_until(self, key: str, now: float) -> float:
        until = self._until.get(key, 0.0)
        return until if until > now else 0.0

    def is_blocked(self, key: str, now: float) -> bool:
        return self.blocked_until(key, now) > 0.0

    def note_success(self, key: str) -> None:
        self._streak[key] = 0

    def note_token_reject(self, key: str, now: float) -> float:
        streak = self._streak.get(key, 0) + 1
        self._streak[key] = streak
        if self.block_seconds > 0 and streak >= self.reject_threshold:
            self._until[key] = now + self.block_seconds
        return self.blocked_until(key, now)
