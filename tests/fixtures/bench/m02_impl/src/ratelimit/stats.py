from __future__ import annotations

import time


class UsageStats:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, object]] = {}

    def _row(self, key: str) -> dict[str, object]:
        return self._data.setdefault(
            key,
            {
                "total_calls": 0,
                "successful_calls": 0,
                "rejected_calls": 0,
                "token_rejects": 0,
                "policy_rejects": 0,
                "peak_rate": 0,
                "blocked_until": 0.0,
                "_stamps": [],
            },
        )

    def record(
        self,
        key: str,
        *,
        ok: bool,
        reason: str | None,
        blocked_until: float,
    ) -> None:
        now = time.monotonic()
        row = self._row(key)
        row["total_calls"] = int(row["total_calls"]) + 1
        stamps = list(row["_stamps"])  # type: ignore[arg-type]
        stamps.append(now)
        stamps = [stamp for stamp in stamps if now - float(stamp) <= 1.0]
        row["_stamps"] = stamps
        row["peak_rate"] = max(int(row["peak_rate"]), len(stamps))
        if ok:
            row["successful_calls"] = int(row["successful_calls"]) + 1
        else:
            row["rejected_calls"] = int(row["rejected_calls"]) + 1
            if reason == "policy":
                row["policy_rejects"] = int(row["policy_rejects"]) + 1
            else:
                row["token_rejects"] = int(row["token_rejects"]) + 1
        row["blocked_until"] = float(blocked_until)

    def get_stats(self, key: str) -> dict[str, float | int]:
        row = self._data.get(key)
        if row is None:
            return {
                "total_calls": 0,
                "successful_calls": 0,
                "rejected_calls": 0,
                "token_rejects": 0,
                "policy_rejects": 0,
                "peak_rate": 0,
                "blocked_until": 0.0,
            }
        until = float(row["blocked_until"])
        live = until if until > time.monotonic() else 0.0
        return {
            "total_calls": int(row["total_calls"]),
            "successful_calls": int(row["successful_calls"]),
            "rejected_calls": int(row["rejected_calls"]),
            "token_rejects": int(row["token_rejects"]),
            "policy_rejects": int(row["policy_rejects"]),
            "peak_rate": int(row["peak_rate"]),
            "blocked_until": live,
        }
