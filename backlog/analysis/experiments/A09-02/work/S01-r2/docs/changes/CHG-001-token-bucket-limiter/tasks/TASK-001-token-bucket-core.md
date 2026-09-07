---
id: TASK-001
change: CHG-001-token-bucket-limiter
slice: SLICE-01
kind: feature
status: targeting
depends_on: []
requirement_delta: none
spec_refs:
  - docs/spec/_capabilities.yaml
design_ref: null
allowed_paths:
  - src/
forbidden_paths:
  - docs/spec/
---

# TASK-001 — Token Bucket Rate Limiter core

## Outcome

Implement a token bucket rate limiter class exposing `__init__(capacity, refill_rate)`,
`consume(key, tokens=1)`, and time-based proportional refill, satisfying CR-001,
CR-002, CR-003, and CR-004.

## Traceability

- Change/slice: CHG-001-token-bucket-limiter / SLICE-01
- Requirements: CR-001, CR-002, CR-003, CR-004
- Scenarios: SC-001, SC-002, SC-003, SC-004, SC-005

## Specification references (verbatim)

- CR-001: "A limiter can be initialized for a given key with two parameters: `capacity` (maximum token capacity) and `refill_rate` (refill rate in tokens per second)."
- CR-002: "`consume(key, tokens=1)`: If enough tokens are available, deduct the requested amount and return `True`. If not enough tokens are available, leave the balance unchanged and return `False`."
- CR-003: "Elapsed time must be accounted for correctly: tokens are restored proportionally to the elapsed time between calls, but never exceed `capacity`."
- CR-004: "Strict argument validation: negative or zero `capacity` / `refill_rate`, and a `consume` call with `tokens <= 0`, must raise `ValueError`."

## Requirements

1. Constructor accepts `capacity` and `refill_rate`; raises `ValueError` if either is `<= 0` (CR-004).
2. Initial balance equals `capacity` (CR-001).
3. `consume(key, tokens=1)` deducts tokens when available and returns `True` (CR-002, SC-002).
4. `consume` returns `False` and leaves balance unchanged when tokens are insufficient (CR-002, SC-003).
5. Between calls, restore tokens proportional to elapsed time, capped at `capacity` (CR-003, SC-004).
6. `consume` with `tokens <= 0` raises `ValueError` (CR-004, SC-005).

## Test oracle

- Construct with `capacity=5, refill_rate=1`; initial balance is 5 tokens.
- `consume(key)` returns `True`; balance becomes 4.
- After exhausting tokens, `consume(key)` returns `False`; balance stays 0.
- Advance time by 2s at `refill_rate=1`: balance increases by 2, capped at `capacity`.
- Construct with `capacity=0` or `refill_rate=-1`: raises `ValueError`.
- `consume(key, tokens=0)` or `tokens=-1`: raises `ValueError`.

## Unchanged behavior

- No persistence, concurrency, or thread-safety (explicitly out of scope in SLICE-01).
- No acceptance-criteria/test files invented beyond the oracle above.

## Allowed / forbidden

- Allowed: `src/` only (implementation).
- Forbidden: `docs/spec/` (do not modify production law), config, or unrelated files.

## Verification

- Run the oracle checks above with the project's test runner (e.g. `pytest` once a runner is chosen at implementation).
- Confirm no `ValueError` is raised for valid inputs and exactly one for each invalid case.
