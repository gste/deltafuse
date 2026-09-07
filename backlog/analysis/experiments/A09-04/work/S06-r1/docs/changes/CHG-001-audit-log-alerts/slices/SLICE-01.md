---
id: SLICE-01
change: CHG-001-audit-log-alerts
title: Audit log recording of consume events
status: specified
primary_capability: ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-002
  - CR-003
  - CR-006
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 8
---

## Scope

- **In scope:** Record each `consume` event (key, tokens, result, timestamp) into an append-only structured log with size-based rotation (max 10 MB per file); filter out irrelevant `DEBUG internal_gc` and `WARN network` lines so they do not influence logic.
- **Out of scope:** Alerting windowing and threshold logic (separate slice), integration point confirmation with the existing rate limiter.

## Dependencies

- CR-007/CR-008: integration point and target runtime must be confirmed; the audit log must consume events from the rate limiter's `consume` operation.

## Spec references

- `docs/spec/security/ratelimit.md` — `consume(key, tokens)` contract (REQ-RL-02) is the event source.

## Unchanged behavior

- Token-bucket capacity, refill, unknown-key, and is_blocked semantics (REQ-RL-01, 03, 04) are unaffected.

## Risks

- Append-only guarantee and rotation boundary must be enforced at write time.
- Structured format must preserve all four fields for downstream alerting.

## Delta projection

- specification: add audit_log behavior under security.ratelimit.
- catalog: new `monitoring.audit_log` capability entry.
- Decisions: audit log format, rotation strategy, integration point.
- tasks: implement recorder, filter, rotation, tests.
- implementation: new monitoring module under `src/ratelimit`.
- evidence: unit tests for append-only, rotation, and line filtering.
