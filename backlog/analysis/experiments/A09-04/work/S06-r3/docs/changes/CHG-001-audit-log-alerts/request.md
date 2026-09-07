# Change: Audit log and alerting on rejection thresholds

Source: `docs/intake/S06.md` (user request, 2026-09-05).

## Summary

The user wants a new monitoring sub-system built on top of an existing
rate-limiter. Two capabilities are requested:

1. An append-only audit log under `monitoring.audit_log` that records every
   `consume` event (key, tokens, result, timestamp) in a structured form, with
   size-based rotation (max 10 MB per file).
2. An alerting mechanism that, over a sliding 60-second window, counts
   rejected requests per key and emits an alert event when the count exceeds a
   threshold (default 100).

The provided sample log contains ~200 lines with duplicate DEBUG/WARN noise and
events across 12 keys; irrelevant lines must not affect the logic.

## Claims

### CR-001 — observation
The user supplied a sample log fragment (200 lines, with duplicates, irrelevant
DEBUG `internal_gc` lines, and `WARN network retransmit` lines) covering ~12
keys. This is an observed input artifact; its exact contents are not verified
here beyond what is quoted in the source.

### CR-002 — expectation
A sub-system `monitoring.audit_log` must record each `consume` event with at
least: key, tokens, result, and timestamp, in a structured log format.

### CR-003 — expectation
The audit log must be append-only and support size-based rotation with a maximum
of 10 MB per file.

### CR-004 — expectation
Alerting must use a sliding 60-second window and count rejected requests per key;
when the count exceeds a threshold (default 100), an alert event is generated.

### CR-005 — expectation
An alert event must contain: key, window_start, window_end, rejection_count,
threshold.

### CR-006 — constraint
Irrelevant log lines (`DEBUG internal_gc`, `WARN network`) must not influence the
audit/alert logic.

### CR-007 — hypothesis
The rate-limiter already emits `consume` events with `key`, `tokens`, and
`result` fields that can be captured; the exact emit site and format are not
confirmed from product code (unread during intake).

### CR-008 — hypothesis
The existing codebase has a `monitoring` namespace/module into which
`audit_log` should be integrated; location and language are unconfirmed.

## Unknowns

- Exact implementation language, runtime, and existing `monitoring` structure.
- Precise location where `consume` events are emitted.
- Whether "rejected" maps to `result=rejected` in the sample log.
- Storage backend for the audit log (file, external store) beyond "append-only
  with 10 MB rotation".
- Alert sink (where alert events are emitted/observed).
