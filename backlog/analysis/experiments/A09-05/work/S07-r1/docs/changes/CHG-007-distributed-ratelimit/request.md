# Change Request: CHG-007-distributed-ratelimit

## Summary

Add a new capability `infra.distributed_ratelimit`: a distributed Rate Limiter with a Redis backend. The product currently has 15 capabilities in `docs/spec/_capabilities.yaml`. This change introduces a larger-than-average capability (~500 lines of code, 3 specification files, and a dedicated integration test suite).

## Claims

### CR-001 — Observation
The product already exposes 15 capabilities in `docs/spec/_capabilities.yaml`, including `security.ratelimit`, `infra.config_reload`, `monitoring.health_check`, and others. (Source: `docs/intake/S07.md`)

### CR-002 — Expectation
The new capability must support all operations of the original `security.ratelimit` — `init`, `consume`, `get_stats` — but persist state in Redis instead of in-memory storage.

### CR-003 — Expectation
Operations must be atomic via Lua scripts in Redis to guarantee consistency under concurrent access from multiple instances.

### CR-004 — Expectation
Configuration must allow switching between in-memory and distributed backends through `infra.config_reload`.

### CR-005 — Expectation
Redis key TTL must equal `capacity / refill_rate * 2` seconds.

### CR-006 — Expectation
Graceful degradation: when Redis is unavailable, the system must automatically fall back to in-memory backend with a warning log entry.

### CR-007 — Expectation
A health check endpoint via `monitoring.health_check` must verify connectivity to Redis.

### CR-008 — Hypothesis
This capability is significantly larger than the others, expecting approximately 500 lines of code, 3 specification files, and a separate integration test suite.

### Unknowns
- Exact `capacity` and `refill_rate` defaults are not specified; TTL formula depends on these values.
- Interaction semantics between `security.ratelimit` and the new distributed variant (replacement, extension, or parallel) are not fully defined.
