---
id: SLICE-02
change: CHG-001-usage-stats-and-rate-policy
title: Rate policy auto-block (security.rate_policy)
status: blocked-on-decision
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
---

## Scope

- In scope: `security.rate_policy` auto-blocks a key after exceeding a rejection threshold; configurable block period (default 300s); blocked key returns `False` from `consume` without consuming tokens; `is_blocked(key)` returns True during block.
- Out of scope: the usage_stats capability (SLICE-01).

## Dependencies

- SLICE-01 (`monitoring.usage_stats`) for CR-009/CR-010 interaction: stats must count policy-blocked rejections as rejected and expose `blocked_until`.

## Unchanged behavior

- REQ-RL-01..03 token-bucket semantics remain the baseline; this slice adds policy-based blocking on top.

## Open Decisions

- CR-005/CR-013: rejection threshold semantics (consecutive 50 vs cumulative 50) unspecified. Default proposed: 50 consecutive rejected `consume` calls resets on any success; flag for Decision.
- CR-006: default block period 300s, configurable; baseline default accepted.

## Risks

- CR-013: threshold semantics affect both consume behavior and stats accounting; must converge with SLICE-01 before tasks.

## Context budget

- max_tokens: 4000
- max_files: 8
