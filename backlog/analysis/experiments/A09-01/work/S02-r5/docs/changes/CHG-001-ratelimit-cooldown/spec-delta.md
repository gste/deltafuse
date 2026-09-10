---
change: CHG-001-ratelimit-cooldown
status: proposed
slices:
  - SLICE-01
---

## MODIFIED REQ-RL-04 is_blocked

`is_blocked(key)` MUST return `False` for the baseline limiter (no penalty lock).
When `penalty_seconds > 0`, `is_blocked(key)` MUST return `True` while the key is
under penalty and `False` otherwise.

## ADDED REQ-RL-05 Cooldown penalty

When `penalty_seconds > 0`, a failed `consume` (insufficient tokens) MUST place
the key into a blocked state lasting `penalty_seconds`. While blocked, every
`consume` call for that key MUST return `False` immediately, even if tokens have
accumulated during the penalty window. After `penalty_seconds` elapses, the block
is lifted automatically on the next request and normal token-consumption logic
resumes.

## ADDED REQ-RL-06 is_blocked under penalty

`is_blocked(key)` MUST return `True` when the key is currently under penalty and
`False` otherwise.
