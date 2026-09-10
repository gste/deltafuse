---
id: SLICE-01
change: CHG-001-doc-update
title: Update security.ratelimit documentation
status: specified
primary_capability: security.ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md#usage-examples
  - docs/spec/security/ratelimit.md#architectural-decisions
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
  - CR-005
---

## In scope

- Add "Usage Examples" section (3 scenarios) to `docs/spec/security/ratelimit.md`.
- Add "Architectural Decisions" section (Token Bucket vs Leaky Bucket, RFC 2697).
- Fix typo `скокрость` → `скорость` in `refill_rate` description.
- Add CHANGELOG.md entry for the documentation change.

## Out of scope

- Any code, test, or behavioral change (CR-005).

## Dependencies

- None. Reads `docs/spec/security/ratelimit.md` and `CHANGELOG.md`.

## Spec references

- `docs/spec/security/ratelimit.md` (target of edits).
- `docs/spec/README.md` (requirement style, live-spec rules).

## Unchanged behavior

- REQ-RL-01..04 semantics unchanged; only the `refill_rate` wording typo is corrected.

## Risks

- Editing a live spec file; keep edits documentation-only and traceable to this Change.

## Context budget

- max_tokens: 16000, max_files: 24.

## Typed delta

- intent: documentation update
- delta_kind: docs
- requirement_delta: none (no new/changed requirements)
- design_impact: none
- risk: low
- size: small
