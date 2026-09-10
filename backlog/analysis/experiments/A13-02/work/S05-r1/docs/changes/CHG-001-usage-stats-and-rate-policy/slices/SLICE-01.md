---
id: SLICE-01
change: CHG-001-usage-stats-and-rate-policy
title: Usage stats capability and rate policy for security.ratelimit
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
  - CR-008
context_budget:
  max_tokens: 16000
  max_files: 24
---

## In scope
- Extend `security.ratelimit` with per-key usage tracking (total/successful/rejected consume counts, peak load as max calls/sec).
- Add `get_stats(key)` returning a dict of those values.
- Add `security.rate_policy`: block a key for a configurable period (default 300s) after a rejection threshold (e.g. 50 rejected consumes in a row).
- Blocked keys return `False` from `consume` without spending tokens and carry a `blocked_until` label in stats.
- Stats must reflect rejections from both token shortage and policy-based blocking.
- Integration tests verifying the interaction of both changes.

## Out of scope
- Changes to token-bucket capacity/refill semantics (REQ-RL-01/02/03 unchanged).
- New domains or capabilities outside `security.ratelimit`.

## Dependencies
- Requires the live spec `docs/spec/security/ratelimit.md` to be extended with normative requirements for stats and the rate policy before implementation.

## Spec references
- REQ-RL-02 (consume contract) — extended to cover blocked-key behavior.
- REQ-RL-05 (policy block contract) — defines blocked-key consume and `blocked_until` reporting.
- REQ-RL-06 (policy activation) — threshold-based block window.
- REQ-RL-07 (usage stats) — `get_stats(key)` dict contract.
- REQ-RL-08 (rejection accounting) — rejects from token shortage and policy blocking both increment `rejected`.

## Unchanged behavior
- Capacity/refill initialization (REQ-RL-01), unknown-key full capacity (REQ-RL-03).

## Risks
- Peak-load measurement granularity and `blocked_until` semantics are now normatively defined (REQ-RL-07).

## Context budget
- Within configured budget (16000 tokens, 24 files); only selected spec modules and this Change are loaded.
