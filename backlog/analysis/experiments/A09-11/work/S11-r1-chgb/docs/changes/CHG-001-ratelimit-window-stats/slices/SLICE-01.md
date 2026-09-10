---
id: SLICE-01
change: CHG-001-ratelimit-window-stats
title: Add get_window_stats(key) to security.ratelimit
status: analyzing
primary_capability: security.ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
  - CR-005
  - CR-006
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 6
---

## Scope

In scope: add `get_window_stats(key)` returning `{accepted, rejected, remaining_tokens}`; counters reset with existing replenishment; unknown keys return zero counters and current remainder per key-init rules; read-only (no token consumption, no limit change).

Out of scope: changing `consume`, `is_blocked`, capacity/refill behavior, or any persistence format.

## Slice analysis

- **intent**: feature (additive read-only method).
- **delta_kind**: spec + implementation + tests.
- **requirement_delta**: new REQ-RL-05 documenting `get_window_stats` contract and read-only guarantee.
- **design_impact**: none beyond a new method on the existing limiter; no new class/interface required unless one already exposes the API.
- **risk**: low; behavior is additive and isolated.
- **size**: small.

## Dependencies

None. Self-contained within `security.ratelimit`.

## Risks

- CR-006: exact key-initialization rule for `remaining_tokens` must be confirmed against `src/ratelimit` before finalizing REQ-RL-05.
- CR-003: confirm whether `accepted`/`rejected` are cumulative-since-reset or current-window-scoped by inspecting existing reset logic.

## Context budget

~4000 tokens / 6 files: spec module, limiter source, replenishment/reset logic, test roots.
