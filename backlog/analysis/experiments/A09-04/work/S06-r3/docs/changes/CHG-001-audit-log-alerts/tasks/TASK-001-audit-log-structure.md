---
id: TASK-001
change: CHG-001-audit-log-alerts
slice: SLICE-01
kind: feature
status: pending
depends_on: []
requirement_delta: added
spec_refs:
  - docs/spec/security/ratelimit.md#REQ-RL-05
allowed_paths:
  - src/ratelimit/monitoring.py
  - tests/test_audit_log.py
forbidden_paths:
  - docs/spec/
  - docs/decisions/
---

# TASK-001 — Structured append-only audit log sink

## Outcome
Add `src/ratelimit/monitoring.py` exposing `AuditLog` that records each `consume`
event as one structured record containing `key`, `tokens`, `result`, and
`timestamp` (ISO-8601 UTC) to an append-only log, and add a test asserting the
record shape and append-only behavior.

## References
- Change/slice: CHG-001-audit-log-alerts / SLICE-01
- Requirement: docs/spec/security/ratelimit.md#REQ-RL-05
- Intake: docs/intake/S06.md

## Task
1. Implement `AuditLog` in `src/ratelimit/monitoring.py` that appends one record
   per consume event with fields `key`, `tokens`, `result`, `timestamp`.
2. `timestamp` MUST be ISO-8601 UTC.
3. `result` MUST be the boolean outcome of the consume call.
4. Records are appended; existing records are never rewritten or deleted.
5. Add `tests/test_audit_log.py` that drives `consume` and asserts each emitted
   record contains the four fields with correct values.

## Test oracle
A test that calls `consume` for a key with enough tokens (result True) and again
without enough tokens (result False) observes two appended records; each record
has `key`, `tokens`, `result` (True then False), and an ISO-8601 UTC `timestamp`.
Reading the log back yields exactly those records in order with no prior records
modified.

## Unchanged behavior
REQ-RL-01 through REQ-RL-04 rate-limiter semantics MUST remain intact; the audit
log is a side sink and must not alter consume return values.

## Scope
`requirement_delta: added`. Do not implement rotation (TASK-002) or alerting
(out of slice scope).

## Verification
Run the audit-log test suite for this change and confirm it passes; confirm
REQ-RL-01..04 tests still pass.

## Dependencies
None. First ready task.
