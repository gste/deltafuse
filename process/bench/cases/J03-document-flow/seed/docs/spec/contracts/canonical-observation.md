# Baseline canonical observation

`GET /api/documents/{document_id}/flow` returns the canonical deterministic
observation of one document: the exact document, its active version, its
active workflow, open slots, audit sequence and consistency watermark. The
response is read-only; no projection may be repaired through it.

The shape below is the baseline slice of DEC-F for the single-step flow: one
approver role, no supersede states, no expert/registrar slots.

## Canonical form

Members are serialized lexicographically; nulls are explicit, never
omitted. `open_slots` is ordered by the public route order (baseline:
`approver`). `audit_sequence` is ordered by `(sequence, event_id)` and
suppresses duplicate event ids.

```json
{"active_version":{"immutable":true,"version_id":"ver-201"},
 "audit_sequence":[{"event_id":"evt-1005","kind":"j03.workflow.decision-applied","sequence":5}],
 "document":{"document_id":"doc-101"},
 "open_slots":[],
 "watermark":{"audit_sequence":5,"caught_up":true,"document_sequence":3,
              "required_sequence":5,"workflow_sequence":2},
 "workflow":{"route_id":"rte-301","state":"APPROVED"}}
```

(The published fixture is canonical single-line JSON; this block is wrapped
for readability only.)

- `active_version` is `null` for a draft without versions.
- `workflow` is `null` while nothing is under review, otherwise
  `{route_id, state}` with `state` in `PENDING`, `APPROVED`, `REJECTED`.
- `open_slots` contains `{"role": "approver", "assigned_actor_id": ...}`
  while the baseline route is pending, and is empty once it closes.

## Convergence

`caught_up=false` is a valid not-yet-converged projection. Consumers poll a
bounded watermark: the response is converged when `caught_up=true` and every
component sequence (`document_sequence`, `workflow_sequence`,
`audit_sequence`) has reached `required_sequence`. Timestamps never decide
convergence or ordering.
