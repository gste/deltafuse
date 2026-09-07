---
id: DEC-001-monitoring-runtime
change: CHG-001-audit-log-alerts
status: proposed
---

## Context

CR-008 requires a target language, runtime, logging framework, and a location
for the `monitoring` module within the current product structure. The source
request (`docs/intake/S06.md`) and the accepted rate limiter contract
(`docs/spec/security/ratelimit.md`) do not assert any of these. CR-007
confirms the audit log must observe the existing `consume` operation, but the
integration point is unconfirmed (low confidence).

## Decision

The target language, runtime, logging framework, and `monitoring` module
placement are **not yet decided**. Until a runtime is established:

1. The audit log contract (CR-002/CR-003) is specified in runtime-agnostic
   terms: an append-only structured event stream keyed on `key`, `tokens`,
   `result`, and `timestamp`, with size-based rotation at 10 MB per file.
2. Line filtering (CR-006) is specified as: only events carrying a valid
   `consume` result (`ok`/`rejected`) are recorded; `DEBUG internal_gc` and
   `WARN network` lines are excluded.
3. No normative code paths, framework bindings, or module paths are written
   into `docs/spec/**` until a runtime Decision is accepted.

## Open question (returns to /analyze-change)

- What language/runtime does `src/ratelimit` target, and does a logging
  framework already exist in the product?
- Where does `monitoring` belong in the current directory structure?
- What is the confirmed integration point for observing `consume` events?

This Decision does not assert behavior; it defers runtime selection to a human
Decision before tasks are decomposed.
