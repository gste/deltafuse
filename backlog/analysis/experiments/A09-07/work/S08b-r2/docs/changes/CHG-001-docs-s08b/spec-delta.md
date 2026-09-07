---
change: CHG-001-docs-s08b
status: proposed
slices:
  - SLICE-01
added: []
modified:
  - docs/spec/security/ratelimit.md
  - CHANGELOG.md
removed: []
---

## docs/spec/security/ratelimit.md

### MODIFIED — add Usage Examples section

Add a `## Usage Examples` section after the requirements, containing 3 typical
scenarios: initialization, consume with validation, and ValueError handling.

### MODIFIED — add Architectural Decisions section

Add a `## Architectural Decisions` section describing the choice of the Token
Bucket algorithm, referencing RFC 2697 and comparing it with the Leaky Bucket
approach.

### MODIFIED — typo fix in REQ-RL-01

`скокрость` → `скорость` in the `refill_rate` description.

## CHANGELOG.md

### MODIFIED — add documentation entry

Add an entry documenting the documentation change to `docs/spec/security/ratelimit.md`.
