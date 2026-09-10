# Change Request: Audit log and alerting on rejection thresholds

Source: `docs/intake/S06.md` (raw user request, 2026-09-05).

## Summary

The user requests a new monitoring sub-system for the rate limiter product. Two
capabilities are requested:

1. An append-only audit log sub-system (`monitoring.audit_log`) that records each
   `consume` event (key, tokens, result, timestamp) in a structured log, with
   size-based rotation (max 10 MB per file).
2. An alerting mechanism: over a sliding 60-second window, if the number of
   rejected requests for a single key exceeds a threshold (default 100), an
   alert event is generated. The alert must contain `key`, `window_start`,
   `window_end`, `rejection_count`, and `threshold`. Irrelevant log lines
   (DEBUG `internal_gc`, WARN `network`) must not affect the logic.

A sample 48-hour log fragment (200 lines with duplicates, irrelevant records, and
noise) is provided as input for analysis.

## Claims

### CR-001 — observation
The provided log contains `ratelimiter ... action=consume` lines with fields
`key`, `tokens`, `result` (ok/rejected), and `balance`, plus timestamps.

### CR-002 — observation
The log also contains irrelevant lines: `DEBUG internal_gc ...` and `WARN
network retransmit ...`, and duplicate lines.

### CR-003 — expectation
A sub-system `monitoring.audit_log` must record each `consume` event with
`key`, `tokens`, `result`, and `timestamp` in a structured, append-only log.

### CR-004 — constraint
The audit log must support size-based rotation, max 10 MB per file.

### CR-005 — expectation
Over a sliding 60-second window, if the count of rejected requests for a single
key exceeds a threshold (default 100), an alert event must be generated.

### CR-006 — constraint
The alert event must contain `key`, `window_start`, `window_end`,
`rejection_count`, and `threshold`.

### CR-007 — constraint
Irrelevant log lines (`DEBUG internal_gc`, `WARN network`) must not affect the
alerting/audit logic.

### CR-008 — hypothesis
The alerting logic should be derived from the provided log sample; the sample is
provided "for analysis" but no concrete expected outputs are specified.

### CR-009 — unknown
The exact integration point with the existing rate limiter code is not specified
(this phase does not read product code).

### CR-010 — unknown
Acceptance criteria, test expectations, and the precise alerting API are not
specified.

## Recommended next step

`/analyze-change CHG-001-audit-log-alerts`
