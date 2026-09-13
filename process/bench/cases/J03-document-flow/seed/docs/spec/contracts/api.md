# Baseline API contract

Baseline endpoints of the seed. Every mutation endpoint is idempotent by
public operation key and returns the prior observable outcome on exact
replay. Error bodies use the closed vocabulary below; no scored assertion
depends on prose messages.

## Mutations

### POST /api/documents

Creates a draft document.

Rejections: `INVALID_SCHEMA` (400), `IDEMPOTENCY_CONFLICT` (409).

### POST /api/documents/{document_id}/versions

Creates an immutable version of an existing draft.

Rejections: `DOCUMENT_NOT_FOUND` (404), `INVALID_SCHEMA` (400),
`IDEMPOTENCY_CONFLICT` (409).

### POST /api/documents/{document_id}/versions/{version_id}/submit

Submits a version for review; the baseline opens one single-step route.
An immutable version can be submitted only while it is the current review
candidate; re-submitting an already submitted immutable version is
`VERSION_IMMUTABLE` (409).

Rejections: `IDENTITY_MISMATCH` (400), `VERSION_NOT_FOUND` (404),
`VERSION_IMMUTABLE` (409), `INVALID_SCHEMA` (400), `IDEMPOTENCY_CONFLICT` (409).

### POST /api/workflows/{route_id}/decisions

Applies the one approver decision of a pending baseline route. The decision
payload binds `decision_id`, `actor_id`, `role` (`approver`), and `action`
(`APPROVE` or `REJECT`). Any other action string is `UNSUPPORTED_ACTION`
(400), retained as invalid evidence with no transition. A decision applied
to a route that is no longer pending is `IDENTITY_MISMATCH` (400): the
baseline route closes exactly once.

Rejections: `IDENTITY_MISMATCH` (400), `UNSUPPORTED_ACTION` (400),
`INVALID_SCHEMA` (400), `IDEMPOTENCY_CONFLICT` (409).

## Queries

### GET /api/documents/{document_id}/flow

Canonical deterministic observation; see
[canonical-observation.md](canonical-observation.md).

Rejections: `DOCUMENT_NOT_FOUND` (404).

## Error body

```json
{"code": "IDEMPOTENCY_CONFLICT", "operation_id": "op-1004", "details": {}}
```

`code` is a member of the closed baseline vocabulary; `operation_id` is the
stable operation identity that produced the outcome; `details` is an object
of string-to-string entries. Canonical member order is lexicographic.

| Code | HTTP | Meaning |
|---|---|---|
| `INVALID_SCHEMA` | 400 | Malformed, unknown-member or wrong-typed input |
| `IDENTITY_MISMATCH` | 400 | Bound identity does not match the addressed entity or its current state |
| `UNSUPPORTED_ACTION` | 400 | Action string outside the closed baseline vocabulary |
| `DOCUMENT_NOT_FOUND` | 404 | No document with the given id |
| `VERSION_NOT_FOUND` | 404 | No version with the given id |
| `VERSION_IMMUTABLE` | 409 | The version already reached an immutable outcome |
| `IDEMPOTENCY_CONFLICT` | 409 | Operation key replayed with a different canonical payload |

Target-change codes (for example actor/role mismatch beyond the single
approver, or incomplete expert review) do not exist in the baseline
vocabulary and are reserved for the target Change intake.

## Idempotency contract

- A command carries a public operation key. Repeating the same key with the
  same canonical payload returns the prior observable outcome (same stable
  result identity) and adds no domain, audit or outbox effect.
- Repeating the same key with a different canonical payload is
  `IDEMPOTENCY_CONFLICT` (409). It is a client error, not an infrastructure
  retry.
- `event_id` independently deduplicates message deliveries; see
  [events.md](events.md).

## Identity binding

Every workflow command binds the full identity tuple
(`document_id`, `version_id`, `route_id` where applicable). A command whose
bound identity does not match the addressed entity is `IDENTITY_MISMATCH`
and causes no transition.
