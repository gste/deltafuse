---
change: CHG-001-ratelimit-cooldown
status: proposed
slices:
  - SLICE-01
---

## ADDED

### REQ-RL-05 Optional cooldown penalty
When `TokenBucketLimiter` is constructed with `penalty_seconds > 0`, a failed
`consume` (insufficient tokens) transitions the key into a blocked state for
`penalty_seconds`. While blocked, every `consume` call for that key MUST return
`False` immediately, even if tokens have accumulated during the penalty window.

### REQ-RL-06 Automatic block lift
After `penalty_seconds` elapses, the block lifts automatically on the next
`consume` request and normal token-consumption logic resumes.

### REQ-RL-07 is_blocked under penalty
`is_blocked(key)` MUST return `True` while the key is under penalty and `False`
otherwise.

## MODIFIED

### REQ-RL-02 Consume
Extended: when `penalty_seconds > 0` and the key is blocked, `consume` MUST
return `False` without deduction even if tokens are available.

### REQ-RL-04 is_blocked
Clarified: `is_blocked(key)` returns `False` for the baseline limiter (no
penalty lock); REQ-RL-07 governs the penalty-locked state.

## REMOVED

- None.
