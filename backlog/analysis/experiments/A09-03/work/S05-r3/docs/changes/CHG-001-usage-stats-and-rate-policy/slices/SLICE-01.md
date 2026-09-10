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
  - docs/spec/monitoring/usage_stats.md
  - docs/spec/security/ratelimit.md
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-008
  - CR-009
  - CR-010
  - CR-011
  - CR-012
---

## Scope

- In scope: new `monitoring.usage_stats` capability; per-key tracking of total/successful/rejected `consume` calls and peak load; `get_stats(key)` dict; stats must reflect rejections from both token shortage and policy blocking; integration tests for the interaction.
- Out of scope: the `security.rate_policy` auto-block policy itself (SLICE-02).

## Dependencies

- SLICE-02 (`security.rate_policy`) for CR-009/CR-010 interaction: stats must count policy-blocked rejections as rejected and expose `blocked_until`.

## Unchanged behavior

- REQ-RL-01..03 token-bucket semantics remain the baseline; this slice adds observability, not new consume semantics.

## Risks

- CR-011: concrete implementation, existing API, storage model, and registration points unknown; must read `src/ratelimit` before finalizing deltas.

## Context budget

- max_tokens: 4000
- max_files: 8
