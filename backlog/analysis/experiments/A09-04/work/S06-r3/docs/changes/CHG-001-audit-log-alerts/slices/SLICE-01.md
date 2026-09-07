---
id: SLICE-01
change: CHG-001-audit-log-alerts
title: Audit log of consume events with size-based rotation
status: analyzing
primary_capability: ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-002
  - CR-003
  - CR-006
  - CR-007
  - CR-008
depends_on: []
context_budget:
  max_tokens: 6000
  max_files: 12
---

## Slice scope

Record every `consume` event in an append-only structured audit log under
`monitoring.audit_log`, with size-based rotation (max 10 MB per file).

### In scope

- Capture `key`, `tokens`, `result`, and `timestamp` per consume event (CR-002).
- Append-only storage with 10 MB rotation (CR-003).
- Irrelevant log lines must not affect logic (CR-006).

### Out of scope

- Sliding-window alerting (separate slice).
- Alert event payload (CR-005 handled elsewhere).

## Delta projection

| Area | Operation |
|---|---|
| specification | requirement_delta: add audit_log behavior to ratelimit |
| catalog | none |
| Decisions | propose storage backend + rotation policy |
| tasks | none yet |
| tests | add audit-log coverage |
| implementation | add audit sink under monitoring |
| evidence | sample-log analysis |

## Unknowns (non-blocking)

Exact emit site, language/runtime, storage backend, and alert sink are
unconfirmed but do not block this single unambiguous feature slice.
