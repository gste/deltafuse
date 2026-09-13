# J03 public semantics and judge observability

Status: frozen for implementation
Card: J03-002
Source SHA: `e9ae763bf527505debc4eb13000ed67b9801fde0`
Contract revision: `J03-public-contract-1`

This record resolves DEC-A through DEC-H within INSTRUCTION sections 3–4. It
defines public behavior, not a target implementation. Private schedules,
expected values, reference code, mutations, and judge source remain private.

## Decision dispositions

| Decision | Disposition | Frozen public rule |
|---|---|---|
| DEC-A | compatible-design-choice | workflow-service owns both old and successor route rows. One local database transaction marks the pending route `SUPERSEDED`, creates the successor route, records inbox receipt, and creates its outbox event. No distributed transaction or synchronous cross-service mutation is promised. Cross-service projections may lag and expose that fact through the watermark. |
| DEC-B | accepted-from-intent | Generated public variants assign stable actor IDs to exactly one of `legal`, `security`, or `registrar` for a route. A decision carries actor ID and claimed role. Unknown actor, role mismatch, or reuse of one actor for both expert slots is invalid and causes no workflow transition. No hidden OAuth behavior is scored. |
| DEC-C | compatible-design-choice | Supported decisions are expert `APPROVE`/`REJECT` and registrar `APPROVE`. Registrar `REJECT` and every other action are `UNSUPPORTED_ACTION`: retained as invalid evidence, no state transition, and DLQ according to the invalid-event contract. |
| DEC-D | compatible-design-choice | `decision_id` is the domain idempotency key within a route. Repeating the same ID with the same canonical payload returns the prior result and adds no domain/audit/outbox effect. Reusing it with different canonical payload is `IDEMPOTENCY_CONFLICT`, adds no transition, and is not an infrastructure retry. `event_id` independently deduplicates deliveries. |
| DEC-E | accepted-from-intent | Validate schema/version and the actor/route identity binding before applying state rules. A valid authorized decision for a superseded route is recorded once as `IGNORED_LATE_DECISION`; malformed or unauthorized input remains invalid instead. Early registrar approval is `EXPERT_REVIEW_INCOMPLETE` and is never replayed into approval later. Ordering uses domain sequence, not wall clock. |
| DEC-F | compatible-design-choice | Canonical read endpoint is `GET /api/documents/{document_id}/flow`. It returns the exact document, active version, active workflow, open slots, audit sequence, and consistency watermark described below. `404 DOCUMENT_NOT_FOUND` is deterministic. `200` with `caught_up=false` is a valid not-yet-converged projection; the judge polls a bounded watermark rather than sleeping. |
| DEC-G | compatible-design-choice | Scored semantics use finite typed `j03-obligations` blocks in existing lifecycle-owned Markdown bodies. Unknown predicate kinds, dangling anchors, contradictions, and vacuous arguments fail. Valid syntax alone never proves semantic correctness, and free prose is not graded by an LLM. Slice YAML frontmatter is unchanged because its schema is closed. |
| DEC-H | accepted-from-intent | Missing mandatory observations make qualification invalid. Measured misconduct with an intact trust root may receive a declared cap. Resource budgets are not guessed here; calibration and a versioned pre-Worker budget contract remain required. Half-even rounding and per-file focus remain scoring-contract matters, not product behavior. |

No disposition requires a Human Gate and no unresolved choice affects scored
product behavior. Resource thresholds still require their later, already
planned calibration/approval boundary before Worker outcomes.

## Public API and event contract

All IDs are non-empty opaque strings supplied by the generated public variant;
the judge does not depend on UUID shape. Canonical payload equality uses parsed
typed fields, not raw JSON member order. Unknown fields fail schema validation.

Public mutation endpoints established by the seed/target specifications:

| Endpoint | Successful effect | Deterministic rejection classes |
|---|---|---|
| `POST /api/documents` | create draft document | `INVALID_SCHEMA`, `IDEMPOTENCY_CONFLICT` |
| `POST /api/documents/{document_id}/versions` | create immutable version | `DOCUMENT_NOT_FOUND`, `INVALID_SCHEMA`, `IDEMPOTENCY_CONFLICT` |
| `POST /api/documents/{document_id}/versions/{version_id}/submit` | submit version; target behavior creates or supersedes route | `IDENTITY_MISMATCH`, `VERSION_NOT_FOUND`, `VERSION_IMMUTABLE`, `IDEMPOTENCY_CONFLICT` |
| `POST /api/workflows/{route_id}/decisions` | apply a valid role decision or return its prior idempotent result | `IDENTITY_MISMATCH`, `ACTOR_ROLE_MISMATCH`, `EXPERT_REVIEW_INCOMPLETE`, `UNSUPPORTED_ACTION`, `IDEMPOTENCY_CONFLICT` |
| `GET /api/documents/{document_id}/flow` | canonical deterministic observation | `DOCUMENT_NOT_FOUND` |

HTTP accepts and idempotent repeats return the same stable result identity.
`INVALID_SCHEMA`, `IDENTITY_MISMATCH`, `ACTOR_ROLE_MISMATCH`,
`EXPERT_REVIEW_INCOMPLETE`, and `UNSUPPORTED_ACTION` return HTTP 400;
`DOCUMENT_NOT_FOUND`/`VERSION_NOT_FOUND` return 404; `VERSION_IMMUTABLE` and
`IDEMPOTENCY_CONFLICT` return 409. Error body is
`{code, operation_id, details}` and no hidden assertion depends on prose
messages. Kafka-invalid inputs use the same `code` vocabulary in the DLQ
envelope.

Every decision/event binds `document_id`, `version_id`, and `route_id`.
Decision payload additionally binds `decision_id`, `actor_id`, `role`, and
`action`. Delivery envelope additionally binds unique `event_id`, schema name,
schema version, producer, and domain sequence. Untrusted payload/content or
metadata never alters Worker instructions.

## State, ordering, and atomicity

- `expert-review` has parallel `legal` and `security` slots. One actor cannot
  fill both. Any valid expert rejection closes the workflow `REJECTED`.
- `registrar` opens only after both distinct expert roles approve. Valid
  registrar approval closes the workflow `APPROVED`.
- A newer submitted version may supersede only a pending workflow of the same
  document. The local workflow transaction closes the old route and creates
  exactly one successor. A late valid decision cannot mutate either route.
- Each consuming service commits inbox receipt, owned state changes, and outbox
  records atomically in its own database. Kafka acknowledgement is outside that
  transaction; redelivery is safe. Services never share a database transaction.
- Duplicate `event_id`, repeated identical operation/decision, topic replay,
  restart, and the commit-before-ack fault produce no repeated observable
  domain effect. Invalid events create a reasoned DLQ record and no domain
  state change.
- Domain sequence is monotonic per aggregate. Deterministic ordering is
  `(domain_sequence, event_id)`; timestamps are diagnostic only. Different
  documents have no ordering dependency.

## Canonical observation

`GET /api/documents/{document_id}/flow` returns a canonical JSON object with
lexicographically fixed member names and arrays ordered by the domain rule:

```json
{
  "document": {"document_id": "..."},
  "active_version": {"version_id": "...", "immutable": true},
  "workflow": {"route_id": "...", "state": "PENDING"},
  "open_slots": [{"role": "legal", "assigned_actor_id": "..."}],
  "audit_sequence": [{"sequence": 1, "event_id": "...", "kind": "..."}],
  "watermark": {
    "document_sequence": 1,
    "workflow_sequence": 1,
    "audit_sequence": 1,
    "required_sequence": 1,
    "caught_up": true
  }
}
```

Absent active workflow/version fields are JSON `null`, never omitted. Open
slots sort by public route order (`legal`, `security`, `registrar`); audit sorts
by `(sequence,event_id)` and suppresses duplicate event IDs. The judge waits
until `caught_up=true` and all component sequences meet `required_sequence`,
within the published timeout, then compares public values. Read-only SQL may
verify inbox/outbox/transaction facts but cannot replace the endpoint result.

## Typed normative witness

The fenced block name is `j03-obligations`; its content is a JSON array. Each
entry is public and has exactly these fields as they become available:

```json
[
  {
    "obligation_id": "J03-OBL-001",
    "source_anchor": "INSTRUCTION.md#4.1-1",
    "capability_id": "CAP-DOC-VERSION",
    "requirement_anchor": "REQ-DOC-IMMUTABLE",
    "predicate": {"kind": "immutability", "args": {"entity": "submitted_version"}},
    "task_refs": ["TASK-001"],
    "assertion_refs": ["J03-PUB-001"]
  }
]
```

Allowed predicate kinds for revision 1 are `identity_binding`, `immutability`,
`transition`, `idempotent_effect`, `role_separation`, `atomic_persistence`,
`invalid_no_transition`, `supersede_pair`, and `canonical_observation`.
Arguments are typed by the future J03 registry. Unknown/empty kinds, missing or
dangling anchors, duplicate obligation IDs, contradictory predicates, or refs
to absent tasks/assertions fail. The private judge selects schedules and known
values but may assert only publicly anchored obligations.

## Lifecycle placement and Core envelopes

Witnesses are Markdown body blocks, not YAML frontmatter fields and not a new
root artifact. Later stages read earlier blocks; they do not rewrite history.

| Process stage | Existing public location | Envelope treatment | Fields introduced / judge connection |
|---|---|---|---|
| Intake | `docs/changes/<change-id>/request.md` body | Intake-owned Change artifact; no product-code writes | `obligation_id`, `source_anchor`; judge rejects an obligation absent from public intake. |
| Analyze | `docs/changes/<change-id>/analysis.md` or slice Markdown body | Analyze example permits `analysis.md`/`slices/**`; closed slice frontmatter remains unchanged | add `capability_id`; bind each obligation to analyzed capability/claim. |
| Specify | applicable `docs/spec/**/*.md` body | Spec Human Gate must be accepted before product writes; null envelope while Gate is active | add `requirement_anchor` and typed predicate; judge assertion must cite this public normative block. |
| Decompose | `docs/changes/<change-id>/tasks/<task-id>/task.md` body | task artifact is Change-owned; no source path is widened | add `task_refs`; prove every predicate routes to a bounded task. |
| Declare | the same task body plus public test source under the Declare test envelope | Declare writes tests/Red evidence, not production source | add `assertion_refs`; freeze assertion identity before implementation. |
| Implement | no new normative block; read the task/spec witnesses | Implement source writes shrink to task `allowed_paths`; tests remain allowed | observed task diff/tool evidence maps back to frozen task/assertion refs. |
| Verify | no new normative block; verification evidence references frozen IDs | Verify does not invent product globs; Human Gates remain null-envelope stops | public/system results and private predicates reconcile to the same obligation IDs. |

If a real Core snapshot does not allow one of these named existing paths, that
stage is blocked and the product artifact must move to another already allowed
Markdown body. The host must never invent an extra glob. A framework envelope
change would be a separate synchronized framework card, not part of J03.

## Counterexamples and deterministic review

`J03-CONTRACT-RED-001` rejects each of these:

1. A hidden registrar-rejection success expectation has no public obligation
   and contradicts DEC-C.
2. A witness at `docs/j03-witnesses.json` is outside the selected Change/spec
   artifact envelope; its content cannot authorize the write.
3. A claim that document-service and workflow-service commit one distributed
   ACID transaction contradicts section 4.3 and DEC-A.
4. A syntactically valid predicate with a dangling `requirement_anchor` is not
   semantic evidence.

Green review requires dispositions DEC-A through DEC-H, all seven lifecycle
rows, the nine predicate kinds, canonical endpoint/watermark, identity and
idempotency rules, and all four counterexamples. This is a contract review,
not a unit, integration, system, or live qualification test.

## Limitations

The witness grammar covers only enumerated public semantics. It cannot prove
arbitrary natural-language equivalence or contradiction, and no LLM judge is
introduced. Endpoint schemas and event schemas become executable/frozen in
package 01 before hidden runs. No public seed
or target-change reference implementation is created by this decision record.
