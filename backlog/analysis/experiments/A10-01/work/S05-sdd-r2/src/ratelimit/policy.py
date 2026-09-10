from __future__ import annotations


def default_policy(rejection_threshold: int = 5, block_duration: float = 300.0) -> dict:
    """Build a rate policy configuration mapping."""
    return {'rejection_threshold': int(rejection_threshold), 'block_duration': float(block_duration)}


def should_block(consecutive_rejections: int, policy: dict) -> bool:
    """Return True when consecutive rejections reach the policy threshold."""
    return consecutive_rejections >= int(policy.get('rejection_threshold', 5))
