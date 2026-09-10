---
change: CHG-001-doc-update
status: accepted
slices:
  - SLICE-01
added:
  - docs/spec/security/ratelimit.md#usage-examples
  - docs/spec/security/ratelimit.md#architectural-decisions
modified:
  - docs/spec/security/ratelimit.md#req-rl-01-capacity-and-refill
removed: []
---

# Spec Delta — CHG-001-doc-update

> Normative edits to the live specification for Change CHG-001-doc-update.
> Gate: `specified`. Requirement delta: none (documentation-only).

## ADDED

- `docs/spec/security/ratelimit.md` — "Usage Examples" section (3 scenarios:
  Initialization, Consume with validation, Handling `ValueError`).
- `docs/spec/security/ratelimit.md` — "Architectural Decisions" section
  (Token Bucket vs Leaky Bucket, RFC 2697).

## MODIFIED

- `docs/spec/security/ratelimit.md` — `refill_rate` description typo
  `скокрость` → `скорость` (REQ-RL-01 wording only; semantics unchanged).

## REMOVED

- (none)

## Unchanged

- REQ-RL-01..04 semantics unchanged.
- Code, tests, and system behavior unchanged (CR-005).
- `docs/CHANGELOG.md` is a change log, not a live-spec law file; its entry is
  recorded in `docs/changes/CHG-001-doc-update/coverage.yaml` (CR-004), not
  mirrored into `docs/spec/**`.
