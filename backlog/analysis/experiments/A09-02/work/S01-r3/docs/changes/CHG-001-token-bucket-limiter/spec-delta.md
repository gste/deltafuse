---
change: CHG-001-token-bucket-limiter
status: proposed
slices:
  - SLICE-01
added:
  - docs/spec/_capabilities.yaml
  - docs/spec/rate-limiter/requirements.yaml
modified: []
removed: []
---

# Spec Delta — CHG-001-token-bucket-limiter (SLICE-01)

## ADDED

### Capability catalog — `docs/spec/_capabilities.yaml`

- Added domain `rate-limiter` with capability `token-bucket`, requirements
  CR-001..CR-004, and tests CR-001..CR-004.

### Capability module — `docs/spec/rate-limiter/requirements.yaml`

- Added capability module for `token-bucket` under domain `rate-limiter`.
  - CR-001: Limiter initialization with `capacity` and `refill_rate` (SC-001).
  - CR-002: `consume(key, tokens=1)` deducts when available, else unchanged
    balance and `False` (SC-002, SC-003).
  - CR-003: Time-proportional refill capped at `capacity` (SC-004).
  - CR-004: Strict argument validation raising `ValueError` (SC-005, SC-006).

## MODIFIED

None.

## REMOVED

None.
