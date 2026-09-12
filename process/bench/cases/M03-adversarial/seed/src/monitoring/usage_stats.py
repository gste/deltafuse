from __future__ import annotations


class UsageRecorder:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def record(self, event: str) -> None:
        if not event:
            raise ValueError("event name must be a non-empty string")
        self._counts[event] = self._counts.get(event, 0) + 1

    def counts(self) -> dict[str, int]:
        return dict(self._counts)
