# Baseline event contract

Baseline events cross service boundaries through Kafka with an
at-least-once delivery contract; domain effects are made safe by transactional
inbox/outbox tables, never by shared database transactions (baseline slice of
DEC-A). This document defines the delivery envelope and the closed baseline
event catalog at schema version 1.

## Delivery envelope

Every event is one canonical JSON object with these members:

| Member | Type | Rules |
|---|---|---|
| `schema_name` | string | Closed registry name, see catalog below |
| `schema_version` | integer | `1` for the whole baseline; unknown versions are invalid |
| `event_id` | string | Unique delivery identity; deduplicates redelivery/replay |
| `producer` | string | Producing service identity |
| `aggregate_type` | string | `DOCUMENT` or `ROUTE` |
| `aggregate_id` | string | Opaque aggregate identity |
| `domain_sequence` | integer | Monotonic per aggregate, starting at 1 |
| `correlation_id` | string | Identity of the originating operation chain |
| `causation_id` | string\|null | `event_id` of the direct cause; null for a chain root |
| `occurred_at` | string\|null | Diagnostic ISO-8601 instant; never used for ordering |
| `payload` | object | Closed, typed payload of the registered schema |

Deterministic ordering is `(domain_sequence, event_id)` per aggregate.
Different aggregates have no ordering dependency. An event whose schema name
or version is not registered is invalid, is dead-lettered with
`code=INVALID_SCHEMA`, and never causes a domain transition — this applies
explicitly to any target-change schema (supersede, parallel roles), which
the baseline registry does not contain.

## Baseline event catalog (schema version 1)

### j03.document.created

Aggregate: `DOCUMENT`. A draft document was created.

Payload: `document_id` (id), `title` (string, 1..512).

### j03.document.version-created

Aggregate: `DOCUMENT`. An immutable version was created.

Payload: `document_id` (id), `version_id` (id), `content` (string, 1..65536).

### j03.document.version-submitted

Aggregate: `DOCUMENT`. A version was submitted for review.

Payload: `document_id` (id), `version_id` (id).

### j03.workflow.route-created

Aggregate: `ROUTE`. One single-step route opened with exactly one assigned
approver.

Payload: `document_id` (id), `version_id` (id), `route_id` (id),
`approver_actor_id` (id).

### j03.workflow.decision-applied

Aggregate: `ROUTE`. A valid decision was applied, closing the route exactly
once. The resulting state is derived from the action, never an independent
claim.

Payload: `document_id` (id), `version_id` (id), `route_id` (id),
`decision_id` (id, the domain idempotency key within the route),
`actor_id` (id), `role` (`"approver"`), `action` (`APPROVE` | `REJECT`),
`resulting_state` (`APPROVED` | `REJECTED`, follows from `action`).

## Validation rules

- All members of the envelope and of each payload are required unless
  explicitly nullable; unknown members are `INVALID_SCHEMA`.
- JSON booleans are never interchangeable with numbers; the only number type
  is a 64-bit integer; non-integer numbers are not part of the contracts.
- Identifier-shaped values are non-empty, at most 128 characters, and free
  of control characters.
- A payload that contradicts its own schema (for example a
  `resulting_state` that does not follow from `action`) is `INVALID_SCHEMA`.

## Delivery and atomicity

- Consuming services commit inbox receipt, owned state changes and outbox
  records atomically in their own database. Kafka acknowledgement is outside
  that transaction; redelivery is safe.
- Duplicate `event_id`, topic replay, restart, or a commit-before-ack fault
  produces no repeated observable domain effect.
- Invalid events are retained as reasoned DLQ records with the public error
  `code` vocabulary and no domain state change.

## Public compatibility fixtures

[fixtures/events/valid/](fixtures/events/valid) holds one canonical fixture
per baseline event; each fixture decodes and re-encodes byte-identically.
[fixtures/events/invalid/](fixtures/events/invalid) holds rejected
counterexamples named `CODE__description.json`, where `CODE` is the error
code that decoding must reject the file with.
