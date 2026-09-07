# Change Request: Distributed Rate Limiter with Redis backend (S07)

## Summary

The product currently exposes 15 capabilities in `docs/spec/_capabilities.yaml`. This request asks to add a new, significantly larger capability `infra.distributed_ratelimit` — a distributed Rate Limiter backed by Redis. It must support all operations of the existing `security.ratelimit` (init, consume, get_stats) but persist state in Redis instead of in-memory, use atomic Lua scripts for consistency across instances, allow configurable switching between in-memory and distributed backends via `infra.config_reload`, set Redis key TTLs to `capacity / refill_rate * 2` seconds, gracefully degrade to in-memory when Redis is unavailable (with a warning log), and expose a Redis connectivity health check via `monitoring.health_check`. Expected size ~500 lines of code, 3 specification files, and a dedicated integration test suite.

## Claims

### CR-001 — observation
The product already declares 15 capabilities in `docs/spec/_capabilities.yaml`, including `security.ratelimit`, `infra.config_reload`, and `monitoring.health_check`.

### CR-002 — expectation
A new capability `infra.distributed_ratelimit` must be added to the capability catalog.

### CR-003 — expectation
The new capability must support all operations of the existing `security.ratelimit` (init, consume, get_stats), with state stored in Redis instead of in-memory.

### CR-004 — expectation
Redis operations must be atomic via Lua scripts to guarantee consistency under concurrent access from multiple instances.

### CR-005 — expectation
Switching between in-memory and distributed backends must be configurable through `infra.config_reload`.

### CR-006 — expectation
Redis key TTLs must equal `capacity / refill_rate * 2` seconds.

### CR-007 — expectation
On Redis unavailability, the limiter must gracefully degrade to in-memory operation and log a warning.

### CR-008 — expectation
A Redis-connectivity health check must be exposed via `monitoring.health_check`.

### CR-009 — hypothesis
The change is expected to be substantially larger than other capabilities: ~500 lines of code, 3 specification files, and a separate integration test suite.

### CR-010 — constraint
The existing 15 capabilities must remain intact; this change adds a new capability without altering existing behavior beyond the documented backend switch.

### CR-011 — observation (unknown)
Exact values for `capacity` and `refill_rate` are not specified in the source; the TTL formula references them but their defaults or source are unknown.
