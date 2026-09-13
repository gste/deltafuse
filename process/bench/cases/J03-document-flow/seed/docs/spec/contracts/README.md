# Baseline contracts — single-step document flow

Contract revision: `J03-public-contract-1` baseline slice
Source decisions: `packages/00/public-contract-decisions.md` (DEC-A..DEC-H)

These documents define the public contracts of the **baseline seed**: a
working single-step document flow. They encode only the working baseline;
every target behavior (parallel expert review, registrar approval, role
separation between expert slots, and version supersede) is reserved for the
target Change intake and is intentionally absent here.

- [api.md](api.md) — endpoints, error vocabulary, idempotency, identity binding
- [events.md](events.md) — delivery envelope, baseline event catalog, ordering
- [canonical-observation.md](canonical-observation.md) — the canonical read model
- [fixtures/](fixtures/) — public compatibility fixtures

## Rules that hold across all contract documents

1. All identifiers (`document_id`, `version_id`, `route_id`, `decision_id`,
   `actor_id`, `event_id`, `operation_id`, producer) are non-empty opaque
   strings of at most 128 characters without control characters. No consumer
   may depend on UUID shape or any internal structure of an identifier.
2. Canonical serialization is JSON with lexicographically sorted member
   names, no insignificant whitespace, and 64-bit integers as the only
   number type. Canonical payload equality compares parsed typed fields,
   never raw member order.
3. Unknown members, unknown schema names or versions, and type mismatches
   are `INVALID_SCHEMA` rejections; they never mutate state.
4. Deterministic ordering is `(domain_sequence, event_id)` per aggregate.
   Timestamps are diagnostic only.
5. No baseline behavior promises distributed transactions across services.
   Each consuming service commits inbox receipts, owned state and outbox
   records atomically in its own database (baseline slice of DEC-A).
