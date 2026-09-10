---
id: SLICE-01
change: CHG-008-ops-rate-limiter-migration
title: Migrate Rate Limiter deployment config, health check, and runbook to limiter-prod-02
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
---

## In scope
- Update deployment config: hostname `limiter-prod-01` -> `limiter-prod-02`, port `8080` -> `9090`, log path `/var/log/ratelimiter/` -> `/opt/logs/ratelimiter/` (CR-001).
- Update monitoring health check URL `http://limiter-prod-01:8080/health` -> `http://limiter-prod-02:9090/health` (CR-002).
- Update `docs/ops/runbook.md` with new hostname, port, and log path (CR-003).

## Out of scope
- Product code, specifications, and tests (CR-004 constraint). No spec delta.

## Dependencies
- Requires locating the deployment config artifact (unknown: exact path/format). Routing to the correct ops config file is the one open item; not a blocking Decision.

## Spec references
- `docs/spec/security/ratelimit.md` (REQ-RL-01..04) — unchanged; this is an ops migration with no behavioral impact.

## Unchanged behavior
- Token-bucket limiter behavior, capacity, refill, consume, is_blocked all unchanged.

## Risks
- Config file location/format not specified; must confirm the artifact before editing to avoid editing the wrong file.
- Log path change may be a move or addition; confirm intent with ops before editing.

## Context budget
- max_tokens: 16000, max_files: 24
