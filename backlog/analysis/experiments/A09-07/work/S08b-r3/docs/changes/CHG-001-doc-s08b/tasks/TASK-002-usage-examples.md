---
id: TASK-002
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

# TASK-002 — Add Usage Examples section

## Outcome

`docs/spec/security/ratelimit.md` contains a «Usage Examples» section with the
three required scenarios (initialization, consume-with-validation, and
ValueError handling) that match the existing in-file examples.

## Traceability

- Change/slice: CHG-001-doc-s08b / SLICE-01
- Requirement refs: CR-002 (add «Usage Examples» with initialization,
  consume-with-validation, and ValueError-handling scenarios)
- Spec ref: `docs/spec/security/ratelimit.md`

## Steps

1. Open `docs/spec/security/ratelimit.md`.
2. Verify a «Usage Examples» section already exists with the three scenarios
   (Initialization, Consume with validation, Handling of ValueError).
3. Confirm each scenario documents the corresponding behavior:
   - Initialization rejects `capacity <= 0`.
   - `consume` returns True and deducts when tokens suffice, False otherwise.
   - `consume` rejects negative token counts with `ValueError`.
   - `ValueError` does not modify the token balance.
4. If any scenario is missing or incomplete, add it consistent with the
   existing structure and wording.

## Test oracle

```
grep -n «Usage Examples» docs/spec/security/ratelimit.md   # expect present
grep -n «Initialization» docs/spec/security/ratelimit.md   # expect present
grep -n «Consume with validation» docs/spec/security/ratelimit.md  # expect present
grep -n «Handling of ValueError» docs/spec/security/ratelimit.md  # expect present
```

## Unchanged behavior

- No normative behavior is introduced; the section documents existing
  REQ-RL-01/02/03 behavior.
- No code, tests, or system behavior change (CR-006).

## Verification

```
grep -n «Usage Examples» docs/spec/security/ratelimit.md
```
