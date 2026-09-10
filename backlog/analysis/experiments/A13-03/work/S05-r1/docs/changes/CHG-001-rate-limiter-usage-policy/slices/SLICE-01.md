---
id: SLICE-01
change: CHG-001-rate-limiter-usage-policy
title: >-
  Per-key usage statistics capability (monitoring.usage_stats) with get_stats()
status: analyzing
primary_capability: monitoring.usage_stats
related_capabilities:
  - security.ratelimit
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-001
  - CR-002
  - CR-008
  - CR-009
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 6
---

## In scope

- Define `monitoring.usage_stats` capability: per-key tracking of total `consume`
  calls, successful count, denied count, and peak load.
- Define `get_stats(key)` returning a dictionary of these values.
- Define peak load (CR-008) as the maximum number of `consume` calls in any
  one-second window.
- Define the exact data types and key names inside the return dict (CR-009).

## Out of scope

- Policy-based auto-blocking (CR-003/CR-004/CR-010) — separate slice.
- Integration tests (CR-006) — covered in an integration slice.
- Configurable threshold/block duration (CR-007) — separate slice.

## Dependencies

- `security.ratelimit` (existing): `consume(key, tokens)` contract underpins
  what counts as success vs. denial.
- Mutually compatible with the rate-policy slice (CR-005): stats must record
  denials caused by policy blocking too, but that slice owns the blocking
  mechanism.

## Spec references

- `docs/spec/security/ratelimit.md` — REQ-RL-01..04 define consume semantics;
  no live `monitoring` spec exists yet, so this slice proposes a new module.

## Unchanged behavior

- Token-bucket capacity/refill, unknown-key full-capacity, and `is_blocked`
  baseline contract remain as-is.

## Risks

- Peak-load measurement (CR-008) is a sliding-window cost; must bound memory.
- CR-009/CR-010 unknowns must stay consistent with the rate-policy slice's
  `blocked_until` representation (CR-010).

## Context budget

~4000 tokens / 6 files: only ratelimit spec, routing, and schema needed.

## Typed delta

- intent: add capability + method contract
- delta_kind: add
- requirement_delta: new REQ-UMS-01..03 (EARS) for tracking, get_stats(), peak
  load definition
- design_impact: new `monitoring` capability module; new `get_stats(key)` API
- risk: low (observable, no cross-cutting safety)
- size: medium

## Proposed Decisions

- D-001: `get_stats(key)` returns a plain dict with keys `total_consumes`,
  `successful`, `denied`, `peak_load_per_sec` (int/float), values as numbers.
- D-002: peak load uses a tumbling/sliding 1-second window with bounded history.
- D-003: unknown key returns `{}` or zeroed stats from `get_stats`.
