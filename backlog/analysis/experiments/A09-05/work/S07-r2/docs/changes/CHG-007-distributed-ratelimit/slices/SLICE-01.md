---
slice_id: SLICE-01
primary_capability: infra.distributed_ratelimit
related_capabilities:
  - security.ratelimit
  - infra.config_reload
  - monitoring.health_check
claims:
  - CR-002
  - CR-003
  - CR-004
  - CR-006
  - CR-007
status: continue
---

# SLICE-01 — Distributed Rate Limiter Capability

## Outcome
Add `infra.distributed_ratelimit` to the catalog: a Redis-backed token-bucket limiter exposing the same `init`/`consume`/`get_stats` operations as `security.ratelimit`, with atomic Lua operations, TTL = `capacity / refill_rate * 2`, graceful in-memory degradation on Redis unavailability, and a Redis-connectivity health check via `monitoring.health_check`.

## In scope
- New capability entry in `docs/spec/_capabilities.yaml` (infra domain, type: supporting).
- New spec file `docs/spec/infra/distributed_ratelimit.md` with REQ scenarios for init/consume/get_stats, Lua atomicity, TTL formula, degradation behavior, and health-check integration.
- Redis key schema and Lua script contract (state stored in Redis, not in-memory).

## Out of scope
- Backend switching via `infra.config_reload` (separate slice; CR-005).
- Health-check wiring details beyond the contract (CR-008 exposes the check).
- Existing 15 capabilities (CR-010 preserved unchanged).

## Dependencies
- `security.ratelimit` REQ-RL-01..03 semantics must carry over to the distributed variant.
- `infra.config_reload` for the backend switch (CR-005).
- `monitoring.health_check` contract for the Redis connectivity check (CR-008).

## Spec references
- `docs/spec/_capabilities.yaml` (infra domain catalog).
- `docs/spec/security/ratelimit.md` (REQ-RL-01..03).
- `docs/spec/monitoring/health_check.md` (health-check contract).

## Unchanged behavior
- All existing 15 capabilities remain intact (CR-010).
- `security.ratelimit` in-memory behavior unchanged; distributed is additive.

## Risks
- CR-011: `capacity`/`refill_rate` defaults and source unspecified — TTL formula references them but origin is unknown. Low confidence; not blocking for this slice.
- CR-009: ~500 LOC / 3 spec files / dedicated integration tests is a hypothesis, not a requirement.

## Context budget
Spec catalog edit + one new spec file. No code or tests written in this slice.

## Typed delta
- intent: feature
- delta_kind: addition
- requirement_delta: new REQ set for distributed limiter
- design_impact: new infra capability, Redis + Lua contract
- risk: medium (CR-011 unknowns)
- size: large (per CR-009 hypothesis)