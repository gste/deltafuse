---
id: SLICE-01
change: CHG-008-ratelimiter-migration
title: Migrate Rate Limiter deployment coordinates to limiter-prod-02
status: specified
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
  - CR-006
---

## Scope

In scope: update deployment config (hostname, port 8080→9090, log path), monitoring health check URL, and runbook coordinates. Out of scope: code, spec, and test changes.

## Delta

- intent: operational relocation
- delta_kind: config-only
- requirement_delta: none (no spec behavior change)
- design_impact: none
- risk: medium (service downtime during cutover)
- size: small

## Notes

Unknowns (exact config/health-check file paths) are non-blocking for this unambiguous migration; resolve paths during task decomposition. No Decision required.

## Spec Gate

Requirement delta is none. No normative spec edits. docs/spec/security/ratelimit.md (REQ-RL-01..04) fully covers the token-bucket limiter behavior; deployment coordinates, health check URL, and runbook are operational, outside the product specification law.
