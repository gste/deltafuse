---
id: SLICE-01
change: CHG-001-burst-allowance
title: Add optional burst_allowance with single retry on rejection
status: specified
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

In scope: add optional `burst_allowance` (default 0) to `TokenBucketLimiter` init; on a rejected `consume`, grant up to `burst_allowance` extra tokens once and retry within the same call; preserve unchanged behavior when `burst_allowance == 0`.

Out of scope: persistent burst credit carryover across calls, per-key burst counters, config/schema changes, and any change to refill/capacity semantics.

## Slice analysis

- **intent**: feature (additive, backward-compatible).
- **delta_kind**: signature + behavior.
- **requirement_delta**: extend REQ-RL-02 to describe the single-retry path; add a new requirement for `burst_allowance` default and exhaustion semantics.
- **design_impact**: `TokenBucketLimiter.__init__` gains `burst_allowance: int = 0`; `consume` gains one retry using extra tokens when not yet exhausted.
- **risk**: low; behavior unchanged when default. Medium only if "exhausting" semantics are ambiguous.
- **size**: small.

## Normative spec state

- REQ-RL-02 extended with the single-retry burst path.
- REQ-RL-06 added for `burst_allowance` default and exhaustion semantics.
