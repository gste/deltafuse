---
id: SLICE-01
change: CHG-008-ratelimiter-migration
title: Migrate Rate Limiter service coordinates to limiter-prod-02
status: analyzing
primary_capability: ratelimit
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
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 8
---

## Scope

- **In scope:** Update deployment configuration (hostname `limiter-prod-01` -> `limiter-prod-02`, port `8080` -> `9090`, log path `/var/log/ratelimiter/` -> `/opt/logs/ratelimiter/`), monitoring health check URL, and ops runbook with new service coordinates.
- **Out of scope:** Code, specification, or test changes. No cutover window, rollback plan, or validation step is defined for this slice.

## Dependencies

- Requires locating the deployment configuration file(s) holding Rate Limiter settings (unknown in source).

## Spec references

- `docs/spec/security/ratelimit.md` — behavioral spec; unchanged by this migration. No REQ-RL delta.

## Unchanged behavior

- Token-bucket rate limiting behavior (REQ-RL-01 through REQ-RL-04) is unaffected.

## Risks

- Unknown deployment config path(s) may require a follow-up Decision to locate before edits.

## Delta projection

- **Specification:** none
- **Catalog:** none
- **Decisions:** none (unknowns are not blocking Decisions)
- **Tasks:** deployment config edit, health check URL edit, runbook edit
- **Tests:** none
- **Implementation:** config/runbook text edits only
- **Evidence:** post-migration health check verification