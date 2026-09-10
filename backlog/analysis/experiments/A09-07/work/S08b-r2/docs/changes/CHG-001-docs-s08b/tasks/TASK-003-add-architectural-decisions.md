---
id: TASK-003
change: CHG-001-docs-s08b
slice: SLICE-01
kind: maintenance
status: pending
depends_on: []
requirement_delta: modified
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

`docs/spec/security/ratelimit.md` contains a `## Architectural Decisions` section
that documents the Token Bucket choice, references RFC 2697, and compares it with
the Leaky Bucket approach.

## Context

- Change/slice: CHG-001-docs-s08b / SLICE-01
- Requirement refs: CR-003 (expectation)
- Delta: `spec-delta.md` — add Architectural Decisions section
- Note: rationale is documented, not accepted as a product Decision

## Steps

1. Open `docs/spec/security/ratelimit.md`.
2. Append a `## Architectural Decisions` heading at the end of the file.
3. Add a `### Token Bucket algorithm` subsection stating the algorithm is used,
   referencing RFC 2697, and justifying burst tolerance via capacity and
   long-term rate via `refill_rate`.
4. Add a `### Comparison with Leaky Bucket` subsection contrasting Leaky Bucket's
   constant-rate queue with Token Bucket's explicit burst modeling.
5. Do not introduce new requirements, invariants, or behavioral claims.

## Test oracle

- `grep -n '## Architectural Decisions' docs/spec/security/ratelimit.md` matches
  once.
- `grep -n 'RFC 2697' docs/spec/security/ratelimit.md` matches.
- `grep -n 'Leaky Bucket' docs/spec/security/ratelimit.md` matches.

## Unchanged behavior

- No code, tests, or runtime behavior change (CR-007).
- No normative spec content is added or altered.

## Verification

```
grep -n '## Architectural Decisions' docs/spec/security/ratelimit.md
grep -n 'RFC 2697' docs/spec/security/ratelimit.md
grep -n 'Leaky Bucket' docs/spec/security/ratelimit.md
```
