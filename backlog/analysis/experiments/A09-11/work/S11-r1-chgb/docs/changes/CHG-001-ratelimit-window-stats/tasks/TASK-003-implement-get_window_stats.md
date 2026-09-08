---
id: TASK-003
change: CHG-001-ratelimit-window-stats
slice: SLICE-01
kind: feature
status: pending
depends_on:
  - TASK-002
requirement_delta: added
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - src/ratelimit
forbidden_paths:
  - (none beyond allowed scope; do not modify consume/is_blocked/capacity/refill/persistence)
---

# TASK-003 — Implement get_window_stats(key)

## Outcome
`security.ratelimit` exposes `get_window_stats(key)` returning `{accepted, rejected, remaining_tokens}` satisfying REQ-RL-05, REQ-RL-06, and REQ-RL-07, with no token consumption and no limit change.

## Why this third
Requires the finalized contract from TASK-002 and the confirmed rule from TASK-001.

## Context
- Change: CHG-001-ratelimit-window-stats
- Slice: SLICE-01
- Spec refs: docs/spec/security/ratelimit.md (REQ-RL-05, REQ-RL-06, REQ-RL-07)
- Capability: security.ratelimit (code root `src/ratelimit`)

## What to implement
1. Add `get_window_stats(key)` to the class/interface that already exposes the limiter API (confirm in TASK-001 whether such an API exists; if none exists, add the method to `TokenBucketLimiter`).
2. Return a dict with exactly the keys `accepted`, `rejected`, `remaining_tokens`.
3. `accepted`/`rejected` reflect the window counters per REQ-RL-06 semantics confirmed in TASK-001.
4. `remaining_tokens` is computed without mutating state: for a known key, the current remainder; for an unknown key, zero counters and the remainder per the confirmed key-initialization rule (REQ-RL-03 / TASK-001).
5. The method MUST NOT consume tokens, refill, or modify capacity/limits (REQ-RL-05, CR-004). It must be a pure read.

## Allowed symbols
Only touch the rate limiter module under `src/ratelimit`. Do not change `consume`, `is_blocked`, capacity, refill, or any persistence format (out of scope per SLICE-01).

## Test oracle
- Calling `get_window_stats(key)` on a known key returns the live counters and remainder and leaves the token balance unchanged (assert balance before == after).
- Calling on an unknown key returns `{accepted: 0, rejected: 0, remaining_tokens: <full capacity per confirmed rule>}`.
- No side effects: repeated calls return identical results.

## Unchanged behavior
`consume`, `is_blocked`, capacity, and refill behavior are unchanged; persistence format unchanged.

## Verification
- Run the existing suite: `pytest tests/` (or the repo's test command) — all existing tests pass.
- Add or run a focused check that `get_window_stats` does not alter balance after calls.

## Notes
Keep the method additive and isolated. If the existing limiter has no counter storage, add minimal internal state consistent with REQ-RL-06 and note it; do not redesign the limiter.