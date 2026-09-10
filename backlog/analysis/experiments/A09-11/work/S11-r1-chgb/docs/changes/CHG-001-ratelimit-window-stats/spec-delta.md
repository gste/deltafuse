---
change: CHG-001-ratelimit-window-stats
status: proposed
slices:
  - SLICE-01
---

# Spec Delta — CHG-001-ratelimit-window-stats

## Added

- REQ-RL-05 Window statistics — `get_window_stats(key)` contract and read-only guarantee.
- REQ-RL-06 Window counter reset — counters reset with replenishment logic.
- REQ-RL-07 Unknown key statistics — zero counters and current remainder for unknown keys.

## Modified

- `docs/spec/security/ratelimit.md` — appended REQ-RL-05, REQ-RL-06, REQ-RL-07 to the existing module.

## Removed

- (none)
