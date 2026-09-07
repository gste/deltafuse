---
id: SLICE-01
change: CHG-001-doc-s08b
title: Update security.ratelimit documentation
status: specified
primary_capability: ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 6
---

## Scope

In scope: edit `docs/spec/security/ratelimit.md` only — add «Usage Examples»
(initialization, `consume` with validation, `ValueError` handling), add
«Architectural Decisions» (Token Bucket with RFC 2697 reference and Leaky
Bucket comparison), fix the `refill_rate` typo «скокрость» → «скорость».

Out of scope: code, tests, and system behavior (CR-006). CHANGELOG placement
(CR-005) is deferred to a follow-up slice pending the unknowns in request.md.

## Delta projection

- specification: `docs/spec/security/ratelimit.md` gains two sections and one
  typo fix; no normative behavior changes.
- catalog: none.
- Decisions: none (Architectural Decisions is documentation content, not a
  product choice awaiting acceptance).
- tasks: none.
- tests: none.
- implementation: none.
- evidence: none.

## Risks

- CHANGELOG.md location unconfirmed; resolved by deferring CR-005.
- «Architectural Decisions» placement unconfirmed; resolved by placing it in
  `ratelimit.md` per CR-003 wording.

## Notes

Single unambiguous documentation slice; unknowns are non-blocking.
