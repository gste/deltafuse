# Product Context

## Scope

### In scope

- Token Bucket Rate Limiter service managing per-key access-token limits with
  time-based refill and strict argument validation.
- Per-key limiter initialized with `capacity` (maximum token capacity) and
  `refill_rate` (tokens refilled per second).
- `consume(key, tokens=1)` deducts tokens when available and returns a boolean
  result; leaves the balance unchanged and returns `False` when insufficient.
- Proportional time-based refill capped at `capacity`.
- Strict argument validation raising `ValueError` for invalid inputs.

### Out of scope

- Concurrency/thread-safety and per-key locking.
- Time-source injection (wall clock).
- Persistence and key namespace scope.
- Public API shape beyond the documented `consume(key, tokens=1)` contract.

## Actors

- Client: code that instantiates a limiter for a key and calls `consume`.

## System boundaries

- The limiter owns per-key token state and elapsed-time accounting. No external
  systems, data ownership, or trust boundaries are defined for this slice.

## Global invariants

- RQ-INV-1: Token balance never exceeds `capacity`.
- RQ-INV-2: `consume` never drives a balance negative.
- RQ-INV-3: Invalid arguments raise `ValueError` before any state mutation.
