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
  - docs/spec/monitoring/usage_stats.md
claims:
  - CR-002
  - CR-003
  - CR-007
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 8
---

## Scope

- **In scope:** Per-key counters (total, success, reject), peak load (max calls in a 1s window), `get_stats(key)` returning a dict, and correct accounting of rejections from both token shortage and policy blocking.
- **Out of scope:** Auto-block policy (SLICE-02), concrete storage internals, thread-safety details.

## Dependencies

- Depends on `security.ratelimit` (CR-001) existing consume() contract.
- Interacts with `security.rate_policy` (SLICE-02) for CR-007/CR-009.

## Spec references

- `docs/spec/security/ratelimit.md` (REQ-RL-01..04) — baseline behavior to preserve.
- `docs/spec/monitoring/usage_stats.md` (REQ-US-01..04) — new normative behavior for this slice.

## Unchanged behavior

- `consume(key, tokens)` boolean return and token deduction semantics (REQ-RL-02/03).
- `is_blocked(key)` returns False on baseline limiter (REQ-RL-04).

## Risks

- Peak-load window definition (sliding vs fixed 1s) must be pinned; illustrative values in CR-010 are not hard requirements.
- Stats must count rejections from both sources without double-counting when policy blocking is added.

## Delta projection

- **spec:** added `docs/spec/monitoring/usage_stats.md` with REQ ids for counters, peak load, `get_stats`, and rejection accounting.
- **catalog:** added `monitoring` domain + `usage_stats` capability entry.
- **decisions:** none blocking — illustrative values are configurable parameters, not Decisions.
- **tasks/tests:** unit tests for stats; integration tests with SLICE-02 for CR-009.
- **size:** small.

## Recommendation

`/decompose-change CHG-001-usage-stats-and-rate-policy SLICE-01`
