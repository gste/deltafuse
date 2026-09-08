---
id: TASK-004
change: CHG-001-ratelimit-window-stats
slice: SLICE-01
kind: feature
status: pending
depends_on:
  - TASK-003
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - tests
forbidden_paths:
  - (none beyond allowed scope; do not modify production code)
---

# TASK-004 — Verify get_window_stats against spec

## Outcome
Tests covering CR-001 through CR-006 pass, proving REQ-RL-05/06/07 hold: correct fields, read-only guarantee, counter reset alignment, and unknown-key zero counters with confirmed remainder.

## Why this last
Requires the implementation from TASK-003 to execute against.

## Context
- Change: CHG-001-ratelimit-window-stats
- Slice: SLICE-01
- Spec refs: docs/spec/security/ratelimit.md (REQ-RL-05, REQ-RL-06, REQ-RL-07)
- Claims: CR-002, CR-003, CR-004, CR-005, CR-006

## What to test
1. CR-002: `get_window_stats(key)` returns a dict with exactly `accepted`, `rejected`, `remaining_tokens` (no extra keys).
2. CR-004: calling it does not consume tokens and does not modify limits (assert balance/capacity unchanged before and after).
3. CR-003/REQ-RL-06: counters reset in step with the replenishment/reset logic (drive a window reset and assert counters reset as the spec requires).
4. CR-005/REQ-RL-07: unknown key returns `accepted: 0`, `rejected: 0`, and `remaining_tokens` equal to the confirmed key-initialization remainder.
5. CR-006: assert the unknown-key remainder matches the rule confirmed in TASK-001.

## Test oracle
Each test asserts a specific claim; green means the corresponding REQ/claim holds. A red test must map to a concrete spec violation, not an ambiguous expectation.

## Unchanged behavior
Existing `consume`, `is_blocked`, capacity, and refill tests remain green; no production code is altered in this task.

## Verification
- `pytest tests/` (or repo test command) — all tests pass, including the new ones.
- Confirm no test relies on unspecified behavior; all assertions trace to REQ-RL-05/06/07.

## Notes
Do not add scope beyond the six claims. If a claim cannot be tested due to an underspecified rule, record it as a Decision rather than asserting behavior.