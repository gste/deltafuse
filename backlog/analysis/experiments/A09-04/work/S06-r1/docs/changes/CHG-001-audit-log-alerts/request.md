# Change: Audit log and alerting on rejection thresholds

Source: `docs/intake/S06.md` (user request with a 48h system log fragment).

## Summary

The user wants two new sub-systems built on top of an existing rate limiter:

1. A `monitoring.audit_log` subsystem that records every `consume` event
   (key, tokens, result, timestamp) into an append-only structured log with
   size-based rotation (max 10 MB per file).
2. An alerting mechanism that, over a sliding 60-second window, counts
   rejected requests per key and emits an alert event when the count exceeds a
   threshold (default 100). Irrelevant log lines (DEBUG internal_gc, WARN
   network) must not affect the logic.

The provided log is noisy: ~200 lines with duplicates, irrelevant DEBUG/WARN
records, and events across ~12 keys.

## Claims

### CR-001 — observation
A sample log fragment (S06.md) shows `ratelimiter ... action=consume` lines with
fields `key`, `tokens`, `result` (ok/rejected), `balance`, plus unrelated
`DEBUG internal_gc` and `WARN network retransmit` lines.

### CR-002 — expectation
Implement `monitoring.audit_log` that records each `consume` event with
`key`, `tokens`, `result`, and `timestamp` into a structured, append-only log.

### CR-003 — constraint
Audit log must be append-only and support size-based rotation, max 10 MB per
file.

### CR-004 — expectation
Alerting: over a sliding 60-second window, count rejected requests per key;
when the count exceeds a threshold (default 100), emit an alert event.

### CR-005 — constraint
An alert event must contain: `key`, `window_start`, `window_end`,
`rejection_count`, `threshold`.

### CR-006 — constraint
Irrelevant log lines (`DEBUG internal_gc`, `WARN network`) must not influence
the audit/alert logic.

### CR-007 — hypothesis
The existing rate limiter exposes a `consume` operation whose events can be
observed/intercepted to feed the audit log; the exact integration point is
unknown and must be confirmed during analysis.

### CR-008 — unknown
The target language, runtime, logging framework, and where `monitoring` fits
into the current product structure are not specified in the source.

## Excluded

No acceptance criteria, technical design, capability routing, or spec
references are asserted here; those belong to later lifecycle phases.
