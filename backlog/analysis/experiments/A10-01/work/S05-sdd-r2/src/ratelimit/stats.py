from __future__ import annotations


def summarize_stats(stats: dict) -> dict:
    """Return a normalized copy of a stats dict with zero defaults."""
    return {
        'total': int(stats.get('total', 0)),
        'success': int(stats.get('success', 0)),
        'rejected': int(stats.get('rejected', 0)),
        'peak_per_second': int(stats.get('peak_per_second', 0)),
        'blocked_until': stats.get('blocked_until'),
    }
