# Change Request: Distributed Rate Limiter with Redis backend

## Summary

The product currently exposes 15 capabilities in `docs/spec/_capabilities.yaml`. This request asks to add a new capability, `infra.distributed_ratelimit`, a distributed rate limiter backed by Redis. It must support all operations of the existing `security.ratelimit` (init, consume, get_stats) but persist state in Redis instead of in-memory memory. It should use atomic Lua-script operations for consistency under concurrent access from multiple instances, support configurable switching between in-memory and distributed backends via `infra.config_reload`, set Redis key TTL to `capacity / refill_rate * 2` seconds, gracefully degrade to in-memory (with a warning log) when Redis is unavailable, and expose a health check endpoint via `monitoring.health_check` for Redis connectivity.

The requester notes this capability is significantly larger than the others: ~500 lines of code, 3 specification files, and a separate integration test suite.

## Claims

### CR-001 — Observation
The product catalog `docs/spec/_capabilities.yaml` currently lists 15 capabilities, including `security.ratelimit`, `infra.config_reload`, and `monitoring.health_check`. (Source: `docs/intake/S07.md`)

### CR-002 — Expectation
A new capability `infra.distributed_ratelimit` must be added to the catalog. It must support the same operations as `security.ratelimit` — `init`, `consume`, `get_stats` — but store state in Redis rather than in-memory memory.

### CR-003 — Expectation
State operations must be atomic via Lua scripts in Redis to guarantee consistency under concurrent access from multiple instances.

### CR-004 — Expectation
Switching between in-memory and distributed backends must be configurable through `infra.config_reload`.

### CR-005 — Expectation
Redis key TTL must equal `capacity / refill_rate * 2` seconds.

### CR-006 — Expectation
On Redis unavailability, the limiter must gracefully degrade to in-memory operation and log a warning.

### CR-007 — Expectation
A health check endpoint must be exposed via `monitoring.health_check` to verify Redis connectivity.

### CR-008 — Hypothesis
The requester estimates ~500 lines of code, 3 specification files, and a separate integration test suite. This estimate is a hypothesis, not a requirement.

### CR-009 — Constraint
No acceptance criteria, technical design, capability routing, or spec references are asserted here; these are to be determined in later phases.

### CR-010 — Unknown
The exact semantics of `capacity` and `refill_rate` (as used in the TTL formula) are not defined in the source and remain unknown.
