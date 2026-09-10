---
id: SLICE-01
change: CHG-001-docs-s08b
title: Update security.ratelimit module documentation
status: specified
primary_capability: ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
  - CHANGELOG.md
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
  - CR-005
  - CR-006
  - CR-007
  - CR-008
---

## Scope

In scope: documentation-only edits to `docs/spec/security/ratelimit.md` and
`CHANGELOG.md`.

- Add a **Usage Examples** section with 3 scenarios: initialization, consume with
  validation, ValueError handling (CR-002).
- Add an **Architectural Decisions** section on the Token Bucket algorithm,
  referencing RFC 2697 and comparing with Leaky Bucket (CR-003).
- Fix the typo `скокрость` → `скорость` in the `refill_rate` description (CR-004,
  CR-005).
- Add a `CHANGELOG.md` entry documenting the documentation change (CR-006).

Out of scope: any code, test, or behavioral change. No acceptance criteria,
technical design, or capability routing changes (CR-007, CR-008).

## Delta projection

- specification: `docs/spec/security/ratelimit.md` gains Usage Examples +
  Architectural Decisions sections; typo fix; `CHANGELOG.md` gains an entry.
- catalog: none.
- Decisions: none (architectural rationale is documented, not accepted as a
  product Decision).
- tasks: none.
- tests: none.
- implementation: none.
- evidence: none.

## Risks

- Low: risk of drifting into behavioral/design territory. Constrained to
documentation text only.

## Context budget

- max_tokens: 2000
- max_files: 4
