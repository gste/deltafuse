---
id: SLICE-01
change: CHG-007-distributed-ratelimit
primary_capability: infra.distributed_ratelimit
related_capabilities:
  - security.ratelimit
  - infra.config_reload
  - monitoring.health_check
claims:
  - CR-002
  - CR-003
  - CR-004
  - CR-005
  - CR-006
  - CR-007
status: continue
---

# SLICE-01 — Distributed Rate Limiter Capability

## Outcome
Add capability `infra.distributed_ratelimit` supporting `init`, `consume`, `get_stats` with Redis-backed state, atomic Lua operations, configurable backend switching, TTL derived from capacity/refill_rate, graceful in-memory degradation, and a Redis health check.

## In scope
- New capability entry in `_capabilities.yaml` (infra domain, type supporting).
- Spec files for the new capability (init/consume/get_stats, TTL, degradation, health check).
- Atomic Lua-script state operations for multi-instance consistency.
- Configurable in-memory vs distributed backend via `infra.config_reload`.
- Redis key TTL = `capacity / refill_rate * 2` seconds.
- Graceful degradation to in-memory with warning log on Redis unavailability.
- Health check endpoint via `monitoring.health_check` for Redis connectivity.

## Out of scope
- Changes to existing `security.ratelimit` behavior (unchanged).
- Acceptance criteria, technical design, and spec references (determined in later phases per CR-009).
- Size estimate (~500 LOC, 3 spec files, integration suite) — hypothesis only, not a requirement (CR-008).
- Semantics of `capacity`/`refill_rate` — unknown per CR-010, not blocking.

## Dependencies
- `security.ratelimit` — operation contract (init/consume/get_stats) mirrored.
- `infra.config_reload` — backend switching configuration.
- `monitoring.health_check` — Redis connectivity health endpoint.

## Risks
- TTL formula undefined for `capacity`/`refill_rate` semantics (CR-010) — resolve during specification, not blocking.
- Multi-instance atomicity correctness under concurrent Lua execution.

## Context budget
Single slice; bounded to infra.distributed_ratelimit plus three related capabilities. No full-spec or codebase load required.
