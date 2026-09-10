---
change: CHG-001-usage-stats-and-rate-policy
status: accepted
slices:
  - SLICE-01
  - SLICE-02
---

# spec-delta — CHG-001-usage-stats-and-rate-policy

## ADDED

### docs/spec/security/ratelimit.md

- REQ-RL-05 get_stats
  `get_stats(key)` MUST return a dict with per-key counters: `total_consumes`,
  `successful_consumes`, `declined_consumes`, `peak_load` (max consume calls in any
  one-second window), and `blocked_until` (ISO-8601 timestamp while blocked, else null).
  `declined_consumes` counts both token-exhaustion declines and policy-block declines
  without double-counting a single call.

- REQ-RL-06 peak_load
  `peak_load` MUST track the maximum number of `consume` calls observed within any
  single one-second sliding window, updated on every `consume` call.

- REQ-RL-07 rate_policy auto-block
  The limiter SHALL block a key for a configurable period once a consecutive-decline
  threshold is exceeded; the consecutive-decline counter resets on any successful
  `consume`. Default threshold: 50 consecutive declines. Default block duration: 300s.

- REQ-RL-08 blocked consume
  While a key is blocked, `consume(key, tokens)` MUST return False without deducting
  tokens, `is_blocked(key)` MUST return True, and `blocked_until` MUST be populated in
  stats; `blocked_until` MUST be cleared (null) on expiry.

### docs/spec/_capabilities.yaml

- Register capability `monitoring.usage_stats` under domain `monitoring`.
- Register policy `security.rate_policy` under domain `security`.
