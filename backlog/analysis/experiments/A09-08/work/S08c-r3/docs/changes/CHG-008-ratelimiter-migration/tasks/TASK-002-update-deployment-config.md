---
id: TASK-002
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

# Update Rate Limiter deployment configuration

## Outcome
Update every located deployment configuration file so the Rate Limiter service coordinates read `limiter-prod-02`, port `9090`, and log path `/opt/logs/ratelimiter/`, replacing the previous `limiter-prod-01`, `8080`, and `/var/log/ratelimiter/` values.

## Verification oracle
After edits, `grep -rn 'limiter-prod-01'` returns no matches in the edited files, and each edited file contains `limiter-prod-02`, `9090`, and `/opt/logs/ratelimiter/` at the expected keys. No other values in the edited files change.

## Context
- Change/slice: CHG-008-ratelimiter-migration / SLICE-01
- Requirement refs: CR-003 (hostname, port, log path)
- Allowed paths: the specific config file paths identified in TASK-001 (recorded there).
- Forbidden paths: `src/ratelimit`, `tests` — no code or test files are touched.

## Unchanged behavior
Token-bucket rate limiting behavior (REQ-RL-01 through REQ-RL-04) is unaffected.

## Verification commands
```
grep -rn 'limiter-prod-02' <edited-config-paths>
grep -rn 'limiter-prod-01' <edited-config-paths>  # must return nothing
```

## Notes
Edit only the values identified in TASK-001. Do not reformat unrelated lines.
