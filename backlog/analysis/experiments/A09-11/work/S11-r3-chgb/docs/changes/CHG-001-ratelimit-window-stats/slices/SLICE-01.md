---
id: SLICE-01
change: CHG-001-ratelimit-window-stats
title: Add get_window_stats(key) to security.ratelimit
status: specified
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
  - CR-007
---

## Scope

- **In scope:** New public method `get_window_stats(key)` on the token-bucket limiter returning `{accepted, rejected, remaining_tokens}`; reuse existing token-replenishment reset path; unknown-key handling per key-initialization rules.
- **Out of scope:** Changing `consume`, limits, capacity, refill_rate, or the reset logic itself.

## Delta projection

- **spec:** REQ-RL-05 through REQ-RL-08 added to `docs/spec/security/ratelimit.md` documenting the `get_window_stats` contract.
- **catalog:** none.
- **decisions:** none material; CR-007 return-type contract is a low-confidence unknown, not a blocking decision.
- **tasks/tests:** unit tests for known/unknown keys and a no-consume assertion.
- **implementation:** additive method; no design impact beyond one new function.

## Risks

- CR-006/CR-007: exact remainder formula for unknown keys and return-type contract need confirmation against `src/ratelimit` before finalizing REQ-RL-05.

## Context budget

- max_tokens: 4000, max_files: 8
