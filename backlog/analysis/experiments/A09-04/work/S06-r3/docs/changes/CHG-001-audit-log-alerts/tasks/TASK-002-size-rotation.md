---
id: TASK-002
change: CHG-001-audit-log-alerts
slice: SLICE-01
kind: feature
status: pending
depends_on:
  - TASK-001
requirement_delta: added
spec_refs:
  - docs/spec/security/ratelimit.md#REQ-RL-06
allowed_paths:
  - src/ratelimit/monitoring.py
  - tests/test_audit_log.py
forbidden_paths:
  - docs/spec/
  - docs/decisions/
---

# TASK-002 — Size-based rotation of audit log

## Outcome
Extend `AuditLog` to rotate to a new file when a log file reaches 10 MB, and add
a test asserting rotation creates a new file while preserving existing records.

## References
- Change/slice: CHG-001-audit-log-alerts / SLICE-01
- Requirement: docs/spec/security/ratelimit.md#REQ-RL-06
- Depends on: TASK-001 (record shape and append-only sink)

## Task
1. When the active log file reaches or exceeds 10 MB, rotate to a new file
   (e.g., append a suffix/counter to the filename) and continue appending to the
   new file.
2. Existing records in the rotated file MUST NOT be modified or deleted.
3. Rotation is size-based; no time-based rotation.
4. Add `tests/test_audit_log.py` coverage that forces the size limit and asserts
   a new file is created and prior records remain intact and readable.

## Test oracle
After writing enough records to exceed 10 MB, a second log file exists, the
original file's records are unchanged and readable, and subsequent records are
appended to the new file.

## Unchanged behavior
Append-only semantics from TASK-001 MUST hold; rotation only adds files, never
rewrites.

## Scope
`requirement_delta: added`. Do not implement alerting (separate slice).

## Verification
Run the rotation test; confirm the 10 MB boundary triggers a new file and records
are preserved.

## Dependencies
TASK-001
