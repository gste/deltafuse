---
id: SLICE-01
change: CHG-001-burst-allowance
title: Optional burst_allowance retry in TokenBucketLimiter.consume
status: specified
primary_capability: ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md#req-rl-05
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
  - CR-005
---

## In scope
- Add optional `burst_allowance` init parameter (default 0).
- On a rejected consume, if the key has unused `burst_allowance` tokens, grant them once and retry within the same call.
- Retry applies at most once per consume call.

## Out of scope
- Per-key vs global `burst_allowance` resolution (assumed per-key).
- Any change to capacity/refill/consume baseline semantics.

## Dependencies
- `docs/spec/security/ratelimit.md` (REQ-RL-01..05) must remain satisfied.
- `TokenBucketLimiter` source location unconfirmed; verify against `src/ratelimit`.

## Unchanged behavior
- Default `burst_allowance=0` preserves current consume semantics (CR-004).
- REQ-RL-02/03/04 unchanged when no burst tokens remain.

## Risks
- Signature/location of `TokenBucketLimiter` not confirmed from product code.
- Retry could double-deduct if token accounting is not atomic; must grant then retry once.

## Context budget
- max_tokens: 16000, max_files: 24

## Typed delta
- intent: feature
- delta_kind: additive
- requirement_delta: add per-key burst_allowance retry clause to consume
- design_impact: TokenBucketLimiter.__init__ signature + consume retry path
- risk: medium
- size: small
