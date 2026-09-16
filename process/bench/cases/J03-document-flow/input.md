# Change request: managed version supersede and multi-stage parallel approval

Case: J03-document-flow
Status: target intake for the Worker Change
Contract revision: `J03-public-contract-1` (see `docs/spec/contracts/`)

The seed implements a working single-step flow: create a draft, add an
immutable version, submit it into a one-approver route, decide, and observe
the result through the canonical endpoint. This Change extends that product.
It must be executed through the DeltaFuse Process (Intake → Analyze →
Specify → Decompose → Declare → Implement → Verify) exactly like any product
Change. The baseline behavior stays valid throughout (backward
compatibility is a scored requirement).

## Claimed requirements

### Version invariants

- REQ-SUP-001: a submitted version stays immutable.
- REQ-SUP-002: a decision always binds the exact
  `document_id + version_id + route_id` triple.
- REQ-SUP-003: submitting a new version supersedes only a pending route of
  the same document.
- REQ-SUP-004: supersede atomically closes the old route as `SUPERSEDED`
  and creates exactly one successor route, in one local transaction of the
  owning service.
- REQ-SUP-005: a late decision on a superseded route never changes state;
  it is recorded once in the audit as `IGNORED_LATE_DECISION`.

### Approval route

- REQ-ROUTE-001: the route has two stages — `expert-review` with parallel
  `legal` and `security` slots, then `registrar`.
- REQ-ROUTE-002: the registrar stage opens only after both expert roles
  approved.
- REQ-ROUTE-003: repeating a decision with the same `decision_id` and the
  same canonical payload is idempotent and adds no effect.
- REQ-ROUTE-004: one actor can never fill two different roles of one route.
- REQ-ROUTE-005: any expert rejection closes the route as `REJECTED`.
- REQ-ROUTE-006: a registrar approval closes the route as `APPROVED`.
- REQ-ROUTE-007: a registrar event that arrives before expert-review is
  complete is retained as invalid evidence and causes no transition.
- REQ-ROUTE-008: registrar rejection is `UNSUPPORTED_ACTION` (invalid
  evidence, no transition).

### Delivery and transaction invariants

- REQ-DEL-001: Kafka delivery stays at-least-once; duplicates and replays
  never create a repeated observable effect.
- REQ-DEL-002: state update, inbox receipt and outbox creation commit
  atomically in the owning service's own database; services never share a
  transaction.
- REQ-DEL-003: a crash between database commit and Kafka acknowledgement is
  safe.
- REQ-DEL-004: Kafka must not be replaced by synchronous HTTP calls.
- REQ-DEL-005: invalid events go to a DLQ with a reason and no domain state
  change; Kafka payload and metadata are untrusted data.

### Observation

- REQ-OBS-001: the canonical endpoint returns document, active version,
  workflow state (including `SUPERSEDED`), open approval slots and the audit
  sequence in the same deterministic JSON shape as the baseline.

## Normative witness block

Each entry anchors one obligation to its source. Later stages extend these
entries in their own lifecycle-owned blocks (capability at Analyze,
requirement anchor and typed predicate at Specify, task refs at Decompose,
assertion refs at Declare).

```j03-obligations
[
  {"obligation_id": "J03-OBL-001", "source_anchor": "INSTRUCTION.md#4.1-1"},
  {"obligation_id": "J03-OBL-002", "source_anchor": "INSTRUCTION.md#4.1-2"},
  {"obligation_id": "J03-OBL-003", "source_anchor": "INSTRUCTION.md#4.1-3"},
  {"obligation_id": "J03-OBL-004", "source_anchor": "INSTRUCTION.md#4.1-4"},
  {"obligation_id": "J03-OBL-005", "source_anchor": "INSTRUCTION.md#4.1-5"},
  {"obligation_id": "J03-OBL-006", "source_anchor": "INSTRUCTION.md#4.2-1"},
  {"obligation_id": "J03-OBL-007", "source_anchor": "INSTRUCTION.md#4.2-2"},
  {"obligation_id": "J03-OBL-008", "source_anchor": "INSTRUCTION.md#4.2-3"},
  {"obligation_id": "J03-OBL-009", "source_anchor": "INSTRUCTION.md#4.2-4"},
  {"obligation_id": "J03-OBL-010", "source_anchor": "INSTRUCTION.md#4.2-5"},
  {"obligation_id": "J03-OBL-011", "source_anchor": "INSTRUCTION.md#4.2-6"},
  {"obligation_id": "J03-OBL-012", "source_anchor": "INSTRUCTION.md#4.2-7"},
  {"obligation_id": "J03-OBL-013", "source_anchor": "INSTRUCTION.md#4.3-1"},
  {"obligation_id": "J03-OBL-014", "source_anchor": "INSTRUCTION.md#4.3-3"},
  {"obligation_id": "J03-OBL-015", "source_anchor": "INSTRUCTION.md#4.3-4"},
  {"obligation_id": "J03-OBL-016", "source_anchor": "INSTRUCTION.md#4.3-6"},
  {"obligation_id": "J03-OBL-017", "source_anchor": "INSTRUCTION.md#4.3-7"},
  {"obligation_id": "J03-OBL-018", "source_anchor": "INSTRUCTION.md#4.4-1"}
]
```

## Stage-witness syntax (public grammar, revision 1)

Witnesses are fenced blocks named `j03-obligations` whose content is a JSON
array, placed in the body of an already allowed lifecycle artifact (Intake:
this request; Analyze: `analysis.md` or slice body; Specify: applicable
`docs/spec/**/*.md` body; Decompose/Declare: the task body). Each entry has
exactly these fields as they become available:

- `obligation_id` (string, unique across the Change) and `source_anchor`
  (string) — introduced at Intake;
- `capability_id` (string) — added at Analyze;
- `requirement_anchor` (string) and `predicate` (`{"kind": "...", "args":
  {...}}`) — added at Specify;
- `task_refs` (array of task ids) — added at Decompose;
- `assertion_refs` (array of public test/assertion ids) — added at Declare.

Allowed predicate kinds at revision 1: `identity_binding`, `immutability`,
`transition`, `idempotent_effect`, `role_separation`,
`atomic_persistence`, `invalid_no_transition`, `supersede_pair`,
`canonical_observation`. Unknown kinds, dangling anchors, duplicate
obligation ids, contradictions and vacuous arguments are rejected. Valid
syntax alone never proves semantic correctness, and free prose is not
graded by an LLM.

## Out of scope

Nothing else changes. The retired legacy adapter, the archived Change under
`seed/docs/archive/`, and the legacy DTO packages are irrelevant history:
they must not be modified, and modifying them is not part of this Change.
