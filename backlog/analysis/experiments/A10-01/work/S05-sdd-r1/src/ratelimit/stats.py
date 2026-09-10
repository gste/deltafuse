from __future__ import annotations


def summarize(stats: dict) -> dict:
    """Return a normalized view of limiter stats for a key."""
    return {
        'total': int(stats.get('total', 0)),
        'success': int(stats.get('success', 0)),
        'rejected': int(stats.get('rejected', 0)),
        'peak_per_second': int(stats.get('peak_per_second', 0)),
        'blocked_until': stats.get('blocked_until'),
    }


def rejection_rate(stats: dict) -> float:
    total = stats.get('total', 0)
    if total == 0:
        return 0.0
    return stats.get('rejected', 0) / total
