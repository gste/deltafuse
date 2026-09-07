---
change: CHG-001-audit-log-alerts
status: proposed
slices:
  - SLICE-01
---

# Spec Delta — CHG-001-audit-log-alerts

## ADDED

### REQ-RL-05 Audit log of consume events

The rate limiter MUST record every `consume` event to an append-only structured
audit log under `monitoring.audit_log`. Each record MUST contain at least:

- `key` — the limiter key
- `tokens` — tokens requested in the consume call
- `result` — the boolean outcome of the consume call
- `timestamp` — the event time in ISO-8601 UTC

Irrelevant log lines (`DEBUG internal_gc`, `WARN network`) MUST NOT influence the
audit log or alerting logic.

### REQ-RL-06 Audit log rotation

The audit log MUST be append-only and support size-based rotation with a maximum
of 10 MB per file. When a log file reaches the size limit, it MUST be rotated to
a new file; existing records MUST NOT be modified or deleted.

## MODIFIED

### docs/spec/security/ratelimit.md

Append REQ-RL-05 and REQ-RL-06 to the existing requirement list.

## REMOVED

- none
