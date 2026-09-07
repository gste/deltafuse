---
id: SLICE-01
change: CHG-001-usage-stats-and-rate-policy
title: Usage stats + rate policy auto-block (mutually compatible)
status: analyzing
primary_capability: security.ratelimit
related_capabilities:
  - monitoring.usage_stats
  - security.rate_policy
policies:
  - security.rate_policy
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
depends_on: []
context_budget:
  max_tokens: 8000
  max_files: 12
---

## Scope

- **In scope:** per-key usage stats (`consume` count, success/denial counts, peak 1s load) via `get_stats(key)`; auto-block after a threshold of consecutive denied consumes returning `False` without token deduction; `blocked_until` marker in stats; integration tests for the interaction; preserve existing `consume`/`is_blocked` behavior.
- **Out of scope:** persistence across restarts, distributed key namespaces, changing the token-bucket capacity/refill contract, or any non-Rate-Limiter product.

## Dependencies

- CR-001 (monitoring.usage_stats) and CR-002 (security.rate_policy) are implemented together so stats reflect both token-shortage denials and policy-block denials (CR-003).

## Spec references

- `docs/spec/security/ratelimit.md` (REQ-RL-01..04) — baseline behavior to preserve.

## Unchanged behavior

- `consume` still returns `True`/deducts when tokens are available (REQ-RL-02); unknown keys start full (REQ-RL-03); `is_blocked` baseline returns `False` (REQ-RL-04).

## Risks

- Ambiguity in "50 denied in a row" (consecutive vs total) and `blocked_until` semantics (absolute vs relative) — non-blocking; resolved during specify/implementation.
- Stats must not double-count a blocked consume as both a denial and a token deduction.

## Delta projection

- spec: add `monitoring.usage_stats` + `security.rate_policy` modules.
- catalog: register new capabilities in `_capabilities.yaml`.
- Decisions: propose auto-block threshold/duration and stats schema decisions (not accepted).
- tasks/tests: integration test for stats + auto-block interaction (CR-004).
- implementation: extend limiter with stats tracking and block state.
- evidence: integration test results.

## Size

medium