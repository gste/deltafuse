---
id: SLICE-01
change: CHG-007-distributed-ratelimit
title: Distributed rate limiter core capability
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
status: analyzing
---

## Scope

In scope: new capability `infra.distributed_ratelimit` implementing `init`, `consume`, `get_stats` with Redis persistence, atomic Lua operations, in-memory/distributed backend switching, TTL = `capacity / refill_rate * 2` seconds, graceful degradation to in-memory on Redis failure with warning log, and health-check connectivity verification via `monitoring.health_check`.

Out of scope: modifying `security.ratelimit` behavior (unchanged baseline), default `capacity`/`refill_rate` values (unknown, non-blocking), and API rate headers.

## Delta projection

- spec: add `docs/spec/infra/distributed_ratelimit.md` (new capability law).
- catalog: add `infra.distributed_ratelimit` entry to `_capabilities.yaml` with code_roots `src/distributed_ratelimit` and test_roots `tests`.
- Decisions: propose backend-switching semantics and TTL default handling (not accepted).
- tasks: implementation, integration test suite, spec authoring.
- tests: dedicated integration suite for atomicity, degradation, TTL, health check.
- implementation: ~500 LOC across 3 spec files per CR-008 hypothesis.

## Risks

- Concurrency correctness of Lua atomicity under multi-instance load.
- Degradation path must not silently drop rate-limit enforcement.
- TTL formula requires `capacity`/`refill_rate`; defaults unresolved but non-blocking.

## Context budget

Well within 16000 tokens / 24 files. Focused on one capability slice.
