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
  - src/ratelimit
  - tests
  - docs/spec/_capabilities.yaml
---

# TASK-001 — Fix refill_rate typo

## Outcome

The word «скокрость» no longer appears anywhere in `docs/spec/security/ratelimit.md`; the `refill_rate` parameter description reads «скорость пополнения».

## Context

- Change: CHG-001-doc-s08b; Slice: SLICE-01
- Claims: CR-004 (observation), CR-005 (expectation)
- Spec refs: `docs/spec/security/ratelimit.md` (REQ-RL-01 prose)

## Steps

1. Open `docs/spec/security/ratelimit.md`.
2. Locate the `## REQ-RL-01 Capacity and refill` line: `TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0 (скокрость пополнения).`
3. Replace «скокрость» with «скорость» so the line reads: `... (скорость пополнения).`
4. Grep the file for any remaining «скокрость» to confirm none remain.

## Test oracle

- `grep -n «скокрость» docs/spec/security/ratelimit.md` returns no matches.
- `grep -n «скорость» docs/spec/security/ratelimit.md` returns exactly one match on the REQ-RL-01 line.

## Unchanged behavior

- REQ-RL-01 through REQ-RL-04 semantics are identical; only prose spelling changes.
- No other file is modified. No code, tests, or catalog entries touched.

## Verification

```bash
grep -rn «скокрость» docs/spec/security/ratelimit.md   # expect: no output
grep -n «скорость» docs/spec/security/ratelimit.md      # expect: REQ-RL-01 line only
```
