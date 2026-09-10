---
id: SLICE-01
change: CHG-001-token-bucket-limiter
title: Token Bucket Rate Limiter core behavior
status: specified
primary_capability: token-bucket-limiter
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/specifications/token-bucket-limiter.md
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
depends_on: []
context_budget:
  max_tokens: 16000
  max_files: 24
---

## In scope

- Per-key limiter initialization with `capacity` and `refill_rate` (CR-001).
- `consume(key, tokens=1)` token-balance semantics (CR-002).
- Time-based proportional refill capped at `capacity` (CR-003).
- Strict argument validation raising `ValueError` (CR-004).

## Out of scope

- Language/framework selection and file layout (CR-005, open for next phase).
- Persistence and process-scope of state (unknown).
- Global vs. strictly per-key independent state (unknown; per-key init assumed).

## Dependencies

- None. CR-005 (implementation route) is a non-blocking hypothesis.

## Spec references

- [docs/spec/specifications/token-bucket-limiter.md](../../specifications/token-bucket-limiter.md) — CR-001..CR-004 now live in the normative spec.

## Unchanged behavior

- None; this is a new service with no existing behavior.

## Risks

- Unspecified language/framework/layout (CR-005) resolved in next phase, not blocking.
- Ambiguity around global vs. per-key state and persistence; assume per-key independent state.

## Context budget

- `max_tokens: 16000`, `max_files: 24`.

## Typed delta

- intent: feature
- delta_kind: new-implementation
- requirement_delta: add token-bucket-limiter requirements to `docs/spec/**`
- design_impact: new service module; language/layout open
- risk: low (behavior well-specified; environment open)
- size: small
