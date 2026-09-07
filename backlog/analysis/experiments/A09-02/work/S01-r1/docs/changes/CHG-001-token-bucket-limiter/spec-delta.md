---
change: CHG-001-token-bucket-limiter
status: accepted
slices:
  - SLICE-01
added:
  - docs/spec/limiter/requirements.yaml
  - docs/spec/_capabilities.yaml
modified:
  - docs/spec/context.md
removed: []
---

# Spec Delta — CHG-001-token-bucket-limiter

Slice: SLICE-01 (Token Bucket Limiter Core)
Status: accepted

## ADDED

- `docs/spec/limiter/requirements.yaml` — requirements RQ-001..RQ-005 and
  scenarios SC-001..SC-007 covering initialization, consume, proportional
  refill, and strict argument validation.
- `docs/spec/_capabilities.yaml` — `limiter` and `validation` capability
  routing entries.

## MODIFIED

- `docs/spec/context.md` — In scope extended with per-key limiter
  initialization parameters and the `consume(key, tokens=1)` contract; global
  invariants RQ-INV-1..RQ-INV-3 added.

## REMOVED

- None.
