---
id: TASK-003
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

# TASK-003 — Add Architectural Decisions section

## Outcome

`docs/spec/security/ratelimit.md` contains an «Architectural Decisions» section
describing the Token Bucket choice with an RFC 2697 reference and a comparison
with Leaky Bucket.

## Traceability

- Change/slice: CHG-001-doc-s08b / SLICE-01
- Requirement refs: CR-003 (add «Architectural Decisions» with Token Bucket
  choice, RFC 2697 reference, Leaky Bucket comparison)
- Spec ref: `docs/spec/security/ratelimit.md`

## Steps

1. Open `docs/spec/security/ratelimit.md`.
2. Verify an «Architectural Decisions» section already exists.
3. Confirm it:
   - States the Token Bucket algorithm is used.
   - References RFC 2697.
   - Compares against Leaky Bucket (constant output rate, burst dropping).
   - Justifies Token Bucket for burst tolerance on a client-facing API.
4. If any required element is missing, add it consistent with the existing
   structure and wording.

## Test oracle

```
grep -n «Architectural Decisions» docs/spec/security/ratelimit.md  # expect present
grep -n «RFC 2697» docs/spec/security/ratelimit.md                # expect present
grep -n «Leaky Bucket» docs/spec/security/ratelimit.md            # expect present
```

## Unchanged behavior

- No product choice is being made; this documents an existing design.
- No code, tests, or system behavior change (CR-006).

## Verification

```
grep -n «Architectural Decisions» docs/spec/security/ratelimit.md
```
