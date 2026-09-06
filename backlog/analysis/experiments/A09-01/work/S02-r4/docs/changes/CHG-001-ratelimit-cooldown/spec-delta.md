---
change: CHG-001-ratelimit-cooldown
status: proposed
slices:
  - SLICE-01
---

# Spec Delta — CHG-001-ratelimit-cooldown

## ADDED

### REQ-RL-05 Penalty lock
When `TokenBucketLimiter` is initialized with `penalty_seconds > 0`, a failed
`consume` (insufficient tokens) transitions the key into a blocked state lasting
`penalty_seconds`. While blocked, `consume` for that key MUST return `False`
immediately, even if tokens have accumulated. The block auto-clears after the
penalty window on the next request, restoring normal spending logic. The block
timer starts at the failed `consume` call.

### REQ-RL-06 is_blocked under penalty
`is_blocked(key)` MUST return `True` when the key is currently under penalty and
`False` otherwise.

## MODIFIED

### REQ-RL-01 Capacity and refill
`TokenBucketLimiter` initialization now accepts an optional `penalty_seconds`
parameter with a default value of `0.0`.

## REMOVED

- None
