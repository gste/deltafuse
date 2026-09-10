---
change: CHG-001-ratelimit-window-stats
status: accepted
slices:
  - SLICE-01
added:
  - REQ-RL-05
  - REQ-RL-06
  - REQ-RL-07
  - REQ-RL-08
---

# Spec Delta — CHG-001-ratelimit-window-stats

Slice: SLICE-01
Status: accepted

## ADDED

- **REQ-RL-05** `get_window_stats(key)` MUST return a dict with exactly the fields
  `accepted`, `rejected`, and `remaining_tokens` for the requested key.
- **REQ-RL-06** Window counters reported by `get_window_stats` MUST be reset
  together with the token-replenishment reset path described in REQ-RL-01/REQ-RL-02;
  there is no separate reset path for statistics.
- **REQ-RL-07** Calling `get_window_stats` MUST NOT consume tokens and MUST NOT
  change any limit, capacity, or refill rate.
- **REQ-RL-08** For an unknown key, `get_window_stats` MUST return
  `accepted=0`, `rejected=0`, and `remaining_tokens` equal to the remainder that
  the key-initialization rules (REQ-RL-03) assign to a freshly seen key.
