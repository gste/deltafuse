---
id: TASK-001
change: CHG-001-docs-s08b
slice: SLICE-01
kind: maintenance
status: pending
depends_on: []
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - docs/spec/security/ratelimit.md
forbidden_paths:
  - src/
  - tests/
  - '*.py'
---

## Outcome

The `refill_rate` parameter description in `docs/spec/security/ratelimit.md` no
longer contains the typo; it reads «скорость».

## Context

- Change/slice: CHG-001-docs-s08b / SLICE-01
- Requirement refs: CR-004 (observation), CR-005 (expectation)
- Section: REQ-RL-01 Capacity and refill

## Steps

1. Open `docs/spec/security/ratelimit.md`.
2. Locate the `refill_rate` description inside REQ-RL-01: «скорость пополнения».
3. Replace the misspelled word «скокрость» with «скорость».
4. Do not alter any other text, code, or structure in the file.

## Test oracle

- `grep -n «скорость» docs/spec/security/ratelimit.md` matches exactly one line
  (REQ-RL-01).
- `grep -n «скокрость» docs/spec/security/ratelimit.md` returns no matches.

## Unchanged behavior

- No code, tests, or runtime behavior change (CR-007).
- No other spec text is modified.

## Verification

```
grep -n «скорость» docs/spec/security/ratelimit.md
grep -n «скокрость» docs/spec/security/ratelimit.md
```
