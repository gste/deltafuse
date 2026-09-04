# Specification (SDD Pack)

Sole implementation law for the project. Derived from Init Requirements and accepted ADRs.

## Law reminder
Code follows spec. If code and spec disagree, spec wins.

## Table of Contents
| Document | Scope / Responsibility |
|----------|------------------------|
| [`00-context.md`](./00-context.md) | System overview, actors, boundaries, and high-level architecture |

## Review Tour
1. Read `00-context.md` for domain boundaries and scope.
2. Review specific module specs for interface contracts and invariants.

## Human-Gated Areas
- Security and authentication boundaries
- Public API contract modifications
- Data persistence schema breaking changes
