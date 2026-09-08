---
id: SLICE-01
change: CHG-011-remove-burst
title: Remove burst_allowance from Rate Limiter
status: specified
primary_capability: ratelimit
related_capabilities:
  - documentation
  - testing
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
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 8
---

## Scope

In scope: remove `burst_allowance` from the token-bucket rate limiter's public
constructor, specification, tests, docs, and capabilities catalog; keep all
other rate-limiting behavior unchanged.

Out of scope: any behavioral change to consume/is_blocked beyond the removed
burst feature; external consumer migration (unverified dependency, not
blocking for this refactor).

## Dependencies

- `docs/spec/security/ratelimit.md` REQ-RL-05 is the only spec clause that
  references burst; it must be removed.
- `src/ratelimit` constructor and `tests` must be scanned for burst references.

## Spec references

- `docs/spec/security/ratelimit.md` REQ-RL-05 (Burst retry) — removed.
- REQ-RL-01 through REQ-RL-04 unchanged.

## Unchanged behavior

- Token bucket capacity/refill, consume semantics (REQ-RL-02), unknown-key
  handling (REQ-RL-03), and is_blocked (REQ-RL-04) remain identical.

## Risks

- External consumers may depend on `burst_allowance`; unverified but not
  blocking for a refactor with no observable behavior change beyond removal.
- Broken anchors in docs/catalog if references are not updated consistently.

## Context budget

- ~4000 tokens, ~8 files: read ratelimit spec, catalog, and scan code/test
  roots for burst references only.
