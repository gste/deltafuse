---
id: TASK-001
change: CHG-008-ratelimiter-migration
slice: SLICE-01
kind: maintenance
status: pending
depends_on: []
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - docs/changes/CHG-008-ratelimiter-migration/tasks/TASK-001-locate-deployment-config.md
forbidden_paths: []
---

# Locate Rate Limiter deployment configuration

## Outcome
Locate every file under the repository that holds the Rate Limiter service deployment coordinates and record their exact paths and the current values found in each.

## Verification oracle
A reviewer can open each listed file, confirm the file is under the product root, and see the current values `limiter-prod-01`, `8080`, and `/var/log/ratelimiter/` present in the file. The task is complete when all such files are enumerated.

## Context
- Change/slice: CHG-008-ratelimiter-migration / SLICE-01
- Requirement refs: CR-001 (current coordinates), CR-003 (config update target)
- Allowed paths: only this task file for recording findings; no production files are edited here.
- Forbidden paths: none yet; production config files are read-only during this task.

## Unchanged behavior
Token-bucket rate limiting behavior (REQ-RL-01 through REQ-RL-04) is unaffected.

## Verification commands
```
grep -rn 'limiter-prod-01' . --include='*.yaml' --include='*.yml' --include='*.json' --include='*.toml' --include='*.ini' --include='*.conf' --include='*.env'
grep -rn '8080' . --include='*.yaml' --include='*.yml' --include='*.json' --include='*.toml' --include='*.ini' --include='*.conf' --include='*.env'
```

## Notes
This is the first ready task. Recommend `/target-task docs/changes/CHG-008-ratelimiter-migration/tasks/TASK-001-locate-deployment-config.md`.
