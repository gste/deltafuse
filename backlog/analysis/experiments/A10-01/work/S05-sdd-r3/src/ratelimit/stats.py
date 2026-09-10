from __future__ import annotations
import time


class UsageStats:
    """Per-key usage statistics collector.

    Tracks total/success/rejected counts and peak per-second load for a key.
    """

    def __init__(self) -> None:
        self._entries: dict[str, dict] = {}

    def record(self, key: str, success: bool) -> None:
        entry = self._entries.setdefault(key, {
            'total': 0,
            'success': 0,
            'rejected': 0,
            'peak_per_sec': 0,
            '_per_sec': {},
            '_last_sec': None,
        })
        entry['total'] += 1
        if success:
            entry['success'] += 1
        else:
            entry['rejected'] += 1

        sec = int(time.time())
        if sec != entry['_last_sec']:
            entry['_per_sec'] = {sec: 1}
            entry['_last_sec'] = sec
        else:
            entry['_per_sec'][sec] = entry['_per_sec'].get(sec, 0) + 1
        if entry['_per_sec'][sec] > entry['peak_per_sec']:
            entry['peak_per_sec'] = entry['_per_sec'][sec]

    def snapshot(self, key: str) -> dict:
        entry = self._entries.get(key)
        if entry is None:
            return {
                'total': 0,
                'success': 0,
                'rejected': 0,
                'peak_per_sec': 0,
            }
        return {
            'total': entry['total'],
            'success': entry['success'],
            'rejected': entry['rejected'],
            'peak_per_sec': entry['peak_per_sec'],
        }

    def reset(self, key: str) -> None:
        self._entries.pop(key, None)
