---
id: TASK-001
change: CHG-001-doc-s08b
slice: SLICE-01
kind: documentation
status: targeting
depends_on: []
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - docs/spec/security/ratelimit.md
forbidden_paths:
  - src/
  - tests/
---

# TASK-001 — Fix refill_rate typo

## Outcome

The `refill_rate` parameter description in `docs/spec/security/ratelimit.md`
no longer contains the typo «скокрость»; it reads «скорость».

## Traceability

- Change/slice: CHG-001-doc-s08b / SLICE-01
- Requirement refs: CR-004 (fix typo «скокрость» → «скорость»)
- Spec ref: `docs/spec/security/ratelimit.md` (REQ-RL-01 line)

## Steps

1. Open `docs/spec/security/ratelimit.md`.
2. Locate the phrase «скорость пополнения» currently misspelled as «скокрость».
3. Replace «скокрость» with «скорость».
4. Confirm no other occurrences of the misspelling remain.

## Test oracle

```
grep -n «скокрость» docs/spec/security/ratelimit.md   # expect no match
grep -n «скорость» docs/spec/security/ratelimit.md    # expect one match
```

## Unchanged behavior

- No other text in the file is altered.
- No code, tests, or system behavior change (CR-006).

## Verification

```
grep -n «скорость» docs/spec/security/ratelimit.md
```
