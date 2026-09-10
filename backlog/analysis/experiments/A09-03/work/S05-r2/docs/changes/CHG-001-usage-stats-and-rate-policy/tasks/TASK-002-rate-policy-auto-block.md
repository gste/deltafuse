---
id: TASK-002
change: CHG-001-usage-stats-and-rate-policy
slice: SLICE-01
kind: feature
status: pending
depends_on:
  - TASK-001
requirement_delta: added
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - src/ratelimit
forbidden_paths: []
---

# TASK-002 — Rate policy auto-block

## Outcome
A key that accumulates a threshold of consecutive denied `consume` calls is
automatically blocked: `consume` returns `False` without deducting tokens, and
`get_stats(key)` includes a `blocked_until` marker (REQ-RL-06, REQ-RL-07).

## Traceability
- Change/slice: CHG-001-usage-stats-and-rate-policy / SLICE-01
- Requirement: REQ-RL-06, REQ-RL-07 (added by this Change)
- Claim: CR-002

## Steps
1. Build on TASK-001's per-key state; add a consecutive-denial counter reset on
   every successful `consume` (REQ-RL-07).
2. On each denial, increment the consecutive-denial counter.
3. When the counter reaches the threshold, set block state with
   `blocked_until` = now + configurable period (default 300 s).
4. In `consume`, if the key is currently blocked (and not expired), return
   `False` immediately without deducting tokens.
5. Expose `blocked_until` in `get_stats(key)` output.
6. Threshold and duration are configurable; keep defaults per REQ-RL-06.

## Test oracle
- Drive a key past the consecutive-denial threshold; assert subsequent
  `consume` returns `False` and token count is unchanged.
- Assert `get_stats(key)['blocked_until']` is present and in the future.
- After the block period elapses, `consume` resumes normal behavior.
- A single success resets the consecutive-denial counter (REQ-RL-07).

## Unchanged behavior
- Non-blocked keys keep REQ-RL-02 consume semantics; `is_blocked` baseline
  contract unchanged for keys that never hit the threshold.
- Stats must not double-count a blocked consume as both denial and deduction.

## Allowed / forbidden
- Allowed: `src/ratelimit` only.
- Forbidden: changing capacity/refill contract, or blocking keys below threshold.

## Verification
- Run the ratelimit test suite; assert block activation, no-token-deduction,
  `blocked_until` presence, expiry, and consecutive-reset behavior.
