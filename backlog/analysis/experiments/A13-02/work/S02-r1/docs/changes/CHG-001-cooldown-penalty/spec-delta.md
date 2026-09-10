---
change: CHG-001-cooldown-penalty
status: proposed
slices:
  - SLICE-01
---

# Specification Delta — CHG-001-cooldown-penalty

Additive delta to `docs/spec/security/ratelimit.md` for the optional cooldown
penalty on `TokenBucketLimiter`.

## ADDED

### REQ-RL-05 penalty_seconds parameter

`TokenBucketLimiter` MUST accept an optional `penalty_seconds` parameter with a
default of `0.0`. Existing initializations without `penalty_seconds` MUST
preserve prior behavior exactly.

### REQ-RL-06 blocked-state transition

WHEN `penalty_seconds > 0` and a `consume(key, tokens)` call fails due to
insufficient tokens, THE SYSTEM SHALL transition the key into a blocked state
lasting `penalty_seconds`.

### REQ-RL-07 immediate block during penalty

WHILE a key is under an active penalty lock, THE SYSTEM SHALL return `False`
from `consume(key, tokens)` immediately, even if tokens have accumulated during
the penalty window.

### REQ-RL-08 auto-lift after penalty

WHEN `penalty_seconds` has fully elapsed for a blocked key, THE SYSTEM SHALL
lift the block on the next `consume` call for that key and resume normal
token-deduction logic.

## MODIFIED

### REQ-RL-04 is_blocked

Baseline: `is_blocked(key)` returns `False` for the baseline limiter (no
penalty lock).

Extended: `is_blocked(key)` MUST return `True` while the key is under an
active penalty lock and `False` otherwise. When `penalty_seconds == 0` (the
default) or no penalty is active, `is_blocked(key)` MUST return `False`.

## REMOVED

- None.

## Unchanged

- REQ-RL-01 (capacity/refill), REQ-RL-02 (consume contract), REQ-RL-03
  (unknown keys start full) are unaffected by the penalty logic.
