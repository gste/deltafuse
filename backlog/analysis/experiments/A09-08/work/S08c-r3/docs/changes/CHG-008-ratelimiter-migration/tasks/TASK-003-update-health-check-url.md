---
id: TASK-003
change: CHG-008-ratelimiter-migration
slice: SLICE-01
kind: maintenance
status: pending
depends_on:
  - TASK-001
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths: []
forbidden_paths:
  - src/ratelimit
  - tests
---

# Update monitoring health check URL

## Outcome
Update the monitoring health check URL from `http://limiter-prod-01:8080/health` to `http://limiter-prod-02:9090/health` in every file that references it.

## Verification oracle
After edits, `grep -rn 'limiter-prod-01:8080/health'` returns no matches, and each file that previously referenced the old URL now contains `http://limiter-prod-02:9090/health`.

## Context
- Change/slice: CHG-008-ratelimiter-migration / SLICE-01
- Requirement refs: CR-004 (health check URL)
- Allowed paths: the specific files identified in TASK-001 that reference the health check URL.
- Forbidden paths: `src/ratelimit`, `tests` — no code or test files are touched.

## Unchanged behavior
Token-bucket rate limiting behavior (REQ-RL-01 through REQ-RL-04) is unaffected.

## Verification commands
```
grep -rn 'limiter-prod-01:8080/health' .  # must return nothing
grep -rn 'limiter-prod-02:9090/health' <edited-paths>
```
