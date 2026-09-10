---
id: SLICE-01
change: CHG-001-audit-log-alerts
title: Audit log and alerting on rejection thresholds
status: analyzing
primary_capability: monitoring
related_capabilities:
  - ratelimit
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
  - CR-005
  - CR-006
  - CR-007
  - CR-008
  - CR-009
  - CR-010
---

## Scope

In scope: design the `monitoring.audit_log` append-only, size-rotated log and the sliding-window rejection alerting mechanism.

Out of scope: modifying the token-bucket limiter core (ratelimit capability), acceptance criteria, and test expectations (CR-010 unknowns).

## Slices

- **Audit log (CR-003, CR-004, CR-007):** record each `consume` event with `key`, `tokens`, `result`, `timestamp`; append-only; rotate at 10 MB; ignore non-consume lines.
- **Alerting (CR-005, CR-006, CR-007):** sliding 60s window per key; alert when rejection count exceeds threshold (default 100); alert payload carries `key`, `window_start`, `window_end`, `rejection_count`, `threshold`.

## Dependencies

- CR-009: integration point with existing rate limiter code is unspecified; alerting consumes `consume` events but the wiring is a later decision.

## Spec references

- `docs/spec/security/ratelimit.md` (consume contract, unchanged behavior).

## Unchanged behavior

- Token-bucket capacity/refill/consume semantics (REQ-RL-01..04) are not modified.

## Risks

- CR-008: alerting logic derived from a noisy log sample without concrete expected outputs; default threshold and window semantics are assumptions pending human confirmation.

## Context budget

- max_tokens: 16000, max_files: 24
