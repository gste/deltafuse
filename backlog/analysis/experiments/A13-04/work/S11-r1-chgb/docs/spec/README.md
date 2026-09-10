# Specification

This directory is the sole implementation law for product behavior.

If code, chat, intake, a Change, a Decision, task, or diff disagrees with the accepted specification, stop and resolve the specification state before implementation.

## Entry points

| Document | Responsibility |
|---|---|
| [`context.md`](./context.md) | Product scope, actors, boundaries, and global invariants |
| [`_capabilities.yaml`](./_capabilities.yaml) | Routing catalog for domains, capabilities, policies, code, and tests |

Add domain directories and capability modules with stable requirement and scenario IDs.

## Review rules

- The live specification describes current required behavior, not change history.
- Normative edits are surgical and traceable to a Change delta.
- Accepted Decisions affecting behavior, contracts, policies, or invariants are mirrored here.
- A human accepts the initial baseline and later normative changes.

## Requirement style (SPEC-003)

Write live requirements with RFC 2119 keywords (`MUST`, `MUST NOT`, `SHOULD`, `MAY`) or Russian equivalents (`ДОЛЖЕН`, `НЕ ДОЛЖЕН`). Prefer EARS so each requirement has a trigger or state and an observable outcome:

- WHEN [trigger] THE SYSTEM SHALL [behavior]
- WHILE [in state] THE SYSTEM SHALL [behavior]
- IF [unwanted condition] THEN THE SYSTEM SHALL [behavior]

EARS is phrasing, not a new file format and not a Specify gate. Vague words ("fast", "convenient") remain invalid. Live files under `docs/spec/**` remain required.

Do not add `.kiro/` specs or Cucumber features as a second source of truth.
