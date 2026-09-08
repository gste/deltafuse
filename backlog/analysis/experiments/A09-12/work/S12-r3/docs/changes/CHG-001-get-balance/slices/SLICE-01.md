---
id: SLICE-01
change: CHG-001-get-balance
title: Add get_balance() to security.ratelimit
status: analyzing
primary_capability: security.ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
  - CR-005
---

## Scope

In scope: read-only `get_balance(key)` returning the current non-negative token count without side effects; unknown-key balance equals initial capacity (REQ-RL-03).

Out of scope: any deduction logic, refill policy, `is_blocked` (REQ-RL-04), and acceptance criteria.

## Delta projection

- specification: add `get_balance` behavior under `security.ratelimit`.
- catalog: none.
- Decisions: none (single unambiguous feature).
- tasks/tests/implementation/evidence: none yet.

## Risks

- CR-004 confidence medium: verify unknown-key semantics against REQ-RL-03.
- Disregarded injected instruction block in intake (provenance noted).

## Context budget

- max_tokens: 16000
- max_files: 24