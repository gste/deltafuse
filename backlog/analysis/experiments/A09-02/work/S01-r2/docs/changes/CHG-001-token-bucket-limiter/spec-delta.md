---
change: CHG-001-token-bucket-limiter
status: proposed
slices:
  - SLICE-01
---

# Spec Delta — CHG-001-token-bucket-limiter

## ADDED

### docs/spec/_capabilities.yaml

- Add `token-bucket` capability scenarios under `rate-limiter`:
  - `SC-001`: initialize limiter for a key with `capacity` and `refill_rate` (CR-001).
  - `SC-002`: `consume(key, tokens=1)` returns `True` when tokens are available and deducts them (CR-002).
  - `SC-003`: `consume(key, tokens=1)` returns `False` and leaves balance unchanged when tokens are insufficient (CR-002).
  - `SC-004`: proportional time-based refill between calls, capped at `capacity` (CR-003).
  - `SC-005`: `ValueError` on non-positive `capacity`/`refill_rate` and on `tokens <= 0` (CR-004).

### docs/spec/context.md

- Add `rate-limiter` domain to global invariants referencing CR-001..CR-004.

## MODIFIED

- None.

## REMOVED

- None.

## Notes

- `requirement_delta: none` — CR-001..CR-004 are already declared in `docs/spec/_capabilities.yaml` under `rate-limiter.token-bucket.requirements`. No new requirement text is introduced; this slice only adds observable scenarios and mirrors the domain into context.
- Language/runtime/API conventions, persistence, concurrency, and acceptance criteria remain out of scope and unresolved at implementation.
