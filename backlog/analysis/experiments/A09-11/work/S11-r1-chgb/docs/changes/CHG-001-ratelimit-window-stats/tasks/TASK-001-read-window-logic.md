---
id: TASK-001
change: CHG-001-ratelimit-window-stats
slice: SLICE-01
kind: maintenance
status: pending
depends_on: []
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - src/ratelimit
forbidden_paths:
  - tests
---

# TASK-001 — Inspect existing window/replenishment logic

## Outcome
A written finding in this task's notes (or a short spec-delta note) that states, verbatim or by reference, the exact key-initialization rule for `remaining_tokens` and whether `accepted`/`rejected` counters are cumulative-since-reset or current-window-scoped, derived from the existing `src/ratelimit` implementation.

## Why this first
CR-006 and the open unknowns cannot be resolved by reasoning; they require reading the existing limiter. Tasks 002-004 depend on the confirmed rule and counter semantics before writing code or tests.

## Context
- Change: CHG-001-ratelimit-window-stats
- Slice: SLICE-01
- Spec refs: docs/spec/security/ratelimit.md (REQ-RL-01, REQ-RL-02, REQ-RL-03, REQ-RL-06)
- Capability: security.ratelimit (code root `src/ratelimit`, test root `tests`)

## What to inspect
1. The `TokenBucketLimiter` class in `src/ratelimit`: how an unknown key is initialized (REQ-RL-03: starts at full capacity) and how `remaining_tokens` is derived.
2. The token-replenishment/reset logic: where and how `accepted`/`rejected` counters are reset, and whether they persist across windows or are scoped to the current window (REQ-RL-06, CR-003).
3. Confirm that no window counters currently exist; if they do, note their existing lifecycle.

## Deliverable
- One paragraph stating the confirmed key-initialization rule for `remaining_tokens` (resolves CR-006).
- One paragraph stating counter scoping (cumulative-since-reset vs current-window), resolving the open unknown.
- If the confirmed rule contradicts the spec-delta assumption, flag it for a Decision before writing REQ-RL-05/06/07.

## Test oracle
The finding is correct if it quotes or precisely references the source lines that initialize an unknown key and reset counters, and it is internally consistent with REQ-RL-01/02/03.

## Unchanged behavior
`consume`, `is_blocked`, capacity, and refill behavior must remain unmodified by this inspection.

## Verification
- `python -c "import ast,sys; ast.parse(open('src/ratelimit/__init__.py').read())"` (adjust module path to the actual source file) parses without error.
- No production code is modified; only findings are recorded.

## Notes
Do not edit `src/ratelimit` here. This is read-only investigation. Record the confirmed rule so TASK-002 can encode it into REQ-RL-05/06/07.