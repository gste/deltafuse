---
id: TASK-004
change: CHG-008-ratelimiter-migration
slice: SLICE-01
kind: maintenance
status: pending
depends_on:
  - TASK-002
  - TASK-003
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - docs/ops/runbook.md
forbidden_paths:
  - src/ratelimit
  - tests
---

# Update ops runbook with new service coordinates

## Outcome
Update `docs/ops/runbook.md` so the Rate Limiter service coordinates read server `limiter-prod-02`, port `9090`, log path `/opt/logs/ratelimiter/`, and health check URL `http://limiter-prod-02:9090/health`, replacing the previous limiter-prod-01 values.

## Verification oracle
After edits, `docs/ops/runbook.md` contains `limiter-prod-02`, `9090`, `/opt/logs/ratelimiter/`, and `http://limiter-prod-02:9090/health`, and no longer contains the old `limiter-prod-01` coordinates. No unrelated runbook content changes.

## Context
- Change/slice: CHG-008-ratelimiter-migration / SLICE-01
- Requirement refs: CR-005 (runbook update)
- Allowed paths: `docs/ops/runbook.md`
- Forbidden paths: `src/ratelimit`, `tests` — no code or test files are touched.

## Unchanged behavior
Token-bucket rate limiting behavior (REQ-RL-01 through REQ-RL-04) is unaffected.

## Verification commands
```
grep -rn 'limiter-prod-01' docs/ops/runbook.md  # must return nothing
grep -rn 'limiter-prod-02' docs/ops/runbook.md
```
