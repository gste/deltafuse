---
id: TASK-002
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

`docs/spec/security/ratelimit.md` contains a `## Usage Examples` section with
exactly three scenarios: initialization, consume with validation, and ValueError
handling.

## Context

- Change/slice: CHG-001-docs-s08b / SLICE-01
- Requirement refs: CR-002 (expectation)
- Delta: `spec-delta.md` — add Usage Examples section

## Steps

1. Open `docs/spec/security/ratelimit.md`.
2. Insert a `## Usage Examples` heading after the requirements block
   (after REQ-RL-04, before any existing content).
3. Add three subsections:
   - `### Initialization` — show `TokenBucketLimiter(capacity=10, refill_rate=1)`
     and cite REQ-RL-01.
   - `### Consume with validation` — show a `consume(...)` conditional and cite
     REQ-RL-02.
   - `### ValueError handling` — show a `try/except ValueError` around
     `TokenBucketLimiter(capacity=0)` and state that invalid params raise
     `ValueError`.
4. Do not modify existing requirement text or the typo (handled by TASK-001).

## Test oracle

- `grep -n '## Usage Examples' docs/spec/security/ratelimit.md` matches once.
- `grep -c '^### ' docs/spec/security/ratelimit.md` counts the three scenario
  headings (Initialization, Consume with validation, ValueError handling).
- Each scenario references its requirement ID (REQ-RL-01 / REQ-RL-02).

## Unchanged behavior

- No code, tests, or runtime behavior change (CR-007).
- Existing requirements are not rewritten.

## Verification

```
grep -n '## Usage Examples' docs/spec/security/ratelimit.md
grep -n 'REQ-RL-01\|REQ-RL-02' docs/spec/security/ratelimit.md
```
