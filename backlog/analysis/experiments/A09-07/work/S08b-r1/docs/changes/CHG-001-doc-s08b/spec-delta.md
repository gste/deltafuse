---
change: CHG-001-doc-s08b
status: proposed
slices:
  - SLICE-01
modified:
  - docs/spec/security/ratelimit.md
added:
  - docs/spec/security/ratelimit.md
removed: []
---

# Specification Delta — CHG-001-doc-s08b

Scope: SLICE-01

## MODIFIED

- `docs/spec/security/ratelimit.md` — corrected typo «скокрость» → «скорость» in the `refill_rate` parameter description (REQ-RL-01). Requirement semantics unchanged.

## ADDED

- `docs/spec/security/ratelimit.md` — «Примеры использования» section with 3 scenarios (initialization, consume with verification, ValueError handling).
- `docs/spec/security/ratelimit.md` — «Архитектурные решения» section describing the Token Bucket algorithm choice, referencing RFC 2697 and comparing with Leaky Bucket.

## REMOVED

- None.

## Unchanged

- REQ-RL-01 through REQ-RL-04 semantics unchanged; only a spelling correction in REQ-RL-01 prose.
- No catalog, Decision, or behavior change.

## Sufficiency

- CR-001..CR-005: `docs/spec/security/ratelimit.md` (edited).
- CR-006: `CHANGELOG.md` (edited).
- CR-007, CR-008: no spec change required; behavior unchanged (spec_refs: none).
