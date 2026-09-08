from __future__ import annotations


def default_policy(reject_threshold: int = 50, block_duration: float = 300.0) -> dict:
    """Return the default block-on-threshold policy configuration."""
    return {
        'name': 'rate_policy',
        'reject_threshold': int(reject_threshold),
        'block_duration': float(block_duration),
    }


def evaluate(stats: dict, reject_threshold: int) -> bool:
    """Return True when a key should be blocked based on consecutive rejections.

    The limiter tracks consecutive rejections itself; this helper exposes the
    threshold decision for testing and reuse.
    """
    return stats.get('rejected', 0) >= reject_threshold
