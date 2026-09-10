---
id: SLICE-01
change: CHG-008-ratelimiter-migration
title: Migrate Rate Limiter deployment coordinates to limiter-prod-02
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
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 8
---

## Scope

In scope: Update deployment config (hostname `limiter-prod-02`, port `8080`→`9090`, log path `/var/log/ratelimiter/`→`/opt/logs/ratelimiter/`), health check URL in monitoring, and runbook coordinates.

Out of scope: Code, spec, or test changes; firewall/ingress/client endpoint updates; cutover window, rollback plan, or downtime notifications.

## Delta Projection

- specification: none — no behavioral change.
- catalog: none.
- Decisions: none material; unknowns are not blocking Decisions.
- tasks: update deployment config, update health check URL, update runbook.
- implementation: config and docs edits only.
- tests: none.
- evidence: post-migration health check and runbook verification.

## Risks

- Port change may require firewall/ingress/client updates not specified here; flagged as unknown, not blocking.
- New server IP/DNS not specified; deployment config uses hostname per CR-001.

## Context Budget

4000 tokens / 8 files; single unambiguous operational slice.
