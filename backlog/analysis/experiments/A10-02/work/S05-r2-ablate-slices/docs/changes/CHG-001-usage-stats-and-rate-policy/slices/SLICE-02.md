---
id: SLICE-02
change: CHG-001-usage-stats-and-rate-policy
title: Rate policy auto-block (security.rate_policy)
status: specified
primary_capability: security.rate_policy
related_capabilities:
  - security.ratelimit
  - monitoring.usage_stats
policies:
  - security.rate_policy
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-004
  - CR-005
  - CR-006
  - CR-007
  - CR-008
depends_on:
  - SLICE-01
context_budget:
  max_tokens: 4000
  max_files: 8
---

## In scope
- Block a key for a configurable period (default 300s) after a decline threshold
  (50 consecutive declines) is exceeded.
- Blocked `consume` returns `False` without deducting tokens; `is_blocked(key)` returns True.
- `blocked_until` field populated in stats while blocked; cleared on expiry.
- Consecutive-decline counter resets on a successful consume.

## Out of scope
- Usage-stats counters (SLICE-01).
- Non-consecutive decline policies.

## Dependencies
- SLICE-01 for shared decline accounting and `blocked_until` exposure.

## Unchanged behavior
- REQ-RL-01/02/03 token semantics; block is orthogonal to token accounting.

## Context budget
- max_tokens: 4000, max_files: 8
