---
id: TASK-002
change: CHG-001-ratelimit-window-stats
slice: SLICE-01
kind: feature
status: pending
depends_on:
  - TASK-001
requirement_delta: added
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - docs/spec/security/ratelimit.md
forbidden_paths:
  - src/ratelimit
  - tests
---

# TASK-002 — Finalize spec delta REQ-RL-05/06/07

## Outcome
`docs/spec/security/ratelimit.md` contains REQ-RL-05, REQ-RL-06, and REQ-RL-07 with the confirmed key-initialization rule and counter semantics, consistent with the accepted spec law. `spec-delta.md` reflects the added requirements.

## Why this second
The requirement text must encode the rule confirmed in TASK-001. Writing the spec before confirming the rule (CR-006) risks encoding a wrong assumption.

## Context
- Change: CHG-001-ratelimit-window-stats
- Slice: SLICE-01
- Spec refs: docs/spec/security/ratelimit.md
- Related claims: CR-002, CR-003, CR-005, CR-006

## What to write
Append exactly these requirements to `docs/spec/security/ratelimit.md` (the spec-delta already lists them as added):
- REQ-RL-05 Window statistics — `get_window_stats(key)` returns a dict with exactly `accepted`, `rejected`, `remaining_tokens`; reading MUST NOT consume tokens or modify limits.
- REQ-RL-06 Window counter reset — `accepted`/`rejected` reset together with the token-replenishment logic (use the semantics confirmed in TASK-001).
- REQ-RL-07 Unknown key statistics — unknown key returns `accepted: 0`, `rejected: 0`, and `remaining_tokens` per the confirmed key-initialization rule (from TASK-001).

Ensure the `remaining_tokens` rule in REQ-RL-07 matches the confirmed rule; if TASK-001 surfaced a contradiction, set status to `blocked` and note the Decision needed rather than guessing.

## Test oracle
The appended requirements are unambiguous and each names the exact field, the read-only guarantee, the reset trigger, and the unknown-key behavior. They do not prescribe implementation beyond the existing limiter contract.

## Unchanged behavior
REQ-RL-01 through REQ-RL-04 are untouched; no existing requirement is modified or removed.

## Verification
- `python -c "import yaml; yaml.safe_load(open('docs/spec/security/ratelimit.md'))"` if the file is YAML-front-matter delimited; otherwise confirm the markdown parses and the three REQ IDs are present and unique.
- `grep -n 'REQ-RL-0[567]' docs/spec/security/ratelimit.md` returns exactly one line per ID.

## Notes
Do not expand scope. This task only records the contract; TASK-003 implements it.