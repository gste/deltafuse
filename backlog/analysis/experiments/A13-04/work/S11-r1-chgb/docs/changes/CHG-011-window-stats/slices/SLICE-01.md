---
id: SLICE-01
change: CHG-011-window-stats
title: Window statistics sampling for rate limiter key
status: specified
primary_capability: ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md#req-rl-05
  - docs/spec/security/ratelimit.md#req-rl-06
  - docs/spec/security/ratelimit.md#req-rl-07
  - docs/spec/security/ratelimit.md#req-rl-08
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
depends_on: []
---

## In scope
- Add `get_window_stats(key)` returning `{accepted, rejected, remaining_tokens}`.
- Window counters reset with existing token-refill logic.
- Reads must not spend tokens or change limits.
- Unknown key returns zero counters and current remainder per key-initialization rules.

## Out of scope
- Any token consumption or limit mutation.
- Penalty lock / `is_blocked` behavior (unchanged).

## Dependencies
- Existing `TokenBucketLimiter` implementation under `src/ratelimit` for refill and key-initialization semantics.

## Spec references
- `docs/spec/security/ratelimit.md`: REQ-RL-05 (window stats), REQ-RL-06 (window counter reset), REQ-RL-07 (non-consuming read), REQ-RL-08 (unknown key statistics).

## Unchanged behavior
- `consume`, `is_blocked`, refill timing, and limit semantics.

## Risks
- Remainder for unknown key must follow REQ-RL-03 (full capacity) rather than inventing a value.

## Context budget
- max_tokens: 16000, max_files: 24

## Typed delta
- intent: feature
- delta_kind: add
- requirement_delta: new non-consuming read requirement for window stats
- design_impact: read-only accessor over existing window counters
- risk: medium
- size: small
