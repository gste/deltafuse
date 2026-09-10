---
id: SLICE-01
change: CHG-001-usage-stats-and-rate-policy
title: Usage stats capability (monitoring.usage_stats)
status: specified
primary_capability: monitoring.usage_stats
related_capabilities:
  - security.ratelimit
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-002
  - CR-003
  - CR-006
  - CR-010
depends_on:
  - SLICE-02
context_budget:
  max_tokens: 4000
  max_files: 8
---

## In scope
- Per-key counters: total `consume` calls, successful consumes, declined consumes.
- Peak load metric: max calls observed in any single one-second window.
- `get_stats(key)` returns a dict with the above plus `blocked_until` (null when not blocked).
- Declines counted from both token exhaustion (REQ-RL-02) and policy blocking (REQ-RL-07).

## Out of scope
- Policy auto-block logic (SLICE-02).

## Dependencies
- SLICE-02 for policy-blocked decline accounting (CR-006).

## Unchanged behavior
- REQ-RL-01 capacity/refill, REQ-RL-03 unknown-key full capacity, REQ-RL-04 `is_blocked` baseline.

## Risks
- CR-009: language/data structures/API surface unspecified; must be inferred from `src/ratelimit`.

## Context budget
- max_tokens: 4000, max_files: 8
