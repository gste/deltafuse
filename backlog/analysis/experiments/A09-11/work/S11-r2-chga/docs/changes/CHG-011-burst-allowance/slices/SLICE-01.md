---
id: SLICE-01
change: CHG-011-burst-allowance
title: Optional burst_allowance with single retry on consume
status: analyzing
primary_capability: ratelimit
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
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 6
---

## Scope

- **In scope:** Add optional `burst_allowance` to `TokenBucketLimiter.__init__` (default 0); on a rejected `consume`, if the key still has `burst_allowance` tokens remaining, grant `extra` tokens once and retry within the same call; update `docs/spec/security/ratelimit.md` with the new behavior; add tests.
- **Out of scope:** Changing capacity/refill semantics, per-key vs global policy (defaults to per-key as the limiter already keys by key), and any multi-retry behavior.

## Dependencies

- Requires confirming the exact `TokenBucketLimiter` signature/location and the meaning of `extra` tokens in the codebase (src/ratelimit).

## Spec references

- `docs/spec/security/ratelimit.md` REQ-RL-01/02/03/04 (existing behavior to preserve).

## Unchanged behavior

- `burst_allowance` defaults to 0, so existing consume/reject behavior is preserved (CR-004).

## Risks

- `extra` token semantics unconfirmed; if `extra` is not a real attribute/parameter, the retry path cannot be implemented as described.
- Per-key vs global `burst_allowance` unspecified; defaulting to per-key is consistent with the key-based limiter.

## Context budget

- ~4000 tokens, 6 files: read `TokenBucketLimiter` source, existing tests, and the ratelimit spec only.

## Delta projection

- **spec:** add a REQ describing burst retry (operation: add).
- **catalog:** none.
- **Decisions:** none blocking (per-key default is a minor, non-blocking choice).
- **tasks:** add unit tests for the retry path.
- **implementation:** modify `__init__` and `consume`.
- **evidence:** passing tests covering default and retry behavior.