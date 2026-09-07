---
change: CHG-001-usage-stats-and-rate-policy
status: proposed
slices:
  - SLICE-01
---

# Spec Delta — CHG-001-usage-stats-and-rate-policy

Slice: SLICE-01
Status: proposed

## ADDED

### docs/spec/security/ratelimit.md

- REQ-RL-05 Usage stats. The limiter MUST expose `get_stats(key)` returning a
  dictionary with at least: total `consume` count, successful count, denied
  count, and peak 1-second load (max calls observed within any single second).
  Denials caused by both token shortage and policy-based blocking MUST be
  counted as denials.

- REQ-RL-06 Rate policy auto-block. When a key accumulates a threshold of
  consecutive denied `consume` calls, the limiter MUST automatically block the
  key for a configurable period (default 300 s). A blocked key MUST return
  `False` from `consume` without deducting tokens, and its stats MUST include a
  `blocked_until` marker.

- REQ-RL-07 Consecutive-denial reset. A successful `consume` MUST reset the
  consecutive-denial counter so the auto-block threshold counts only
  consecutive denials.

### docs/spec/_capabilities.yaml

- Register capability `monitoring.usage_stats` (summary: per-key usage
  statistics) under domain `monitoring`, referencing `docs/spec/security/
  ratelimit.md`.

- Register capability `security.rate_policy` (summary: automatic key blocking
  after repeated denials) under domain `security`, referencing
  `docs/spec/security/ratelimit.md`.
