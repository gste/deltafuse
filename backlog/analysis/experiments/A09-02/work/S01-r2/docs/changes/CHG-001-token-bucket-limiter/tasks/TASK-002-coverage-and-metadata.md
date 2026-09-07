---
id: TASK-002
change: CHG-001-token-bucket-limiter
slice: SLICE-01
kind: maintenance
status: targeting
depends_on:
  - TASK-001
requirement_delta: none
spec_refs:
  - docs/spec/_capabilities.yaml
design_ref: null
allowed_paths:
  - docs/changes/CHG-001-token-bucket-limiter/coverage.yaml
  - docs/changes/CHG-001-token-bucket-limiter/change.yaml
forbidden_paths:
  - docs/spec/
---

# TASK-002 — Coverage and task metadata update

## Outcome

Record TASK-001 against each claim in `coverage.yaml` and add task metadata to
`change.yaml` so every slice requirement maps to a resolvable task.

## Traceability

- Change/slice: CHG-001-token-bucket-limiter / SLICE-01
- Requirements: CR-001, CR-002, CR-003, CR-004

## Requirements

1. In `docs/changes/CHG-001-token-bucket-limiter/coverage.yaml`, set `tasks: [TASK-001]` for CR-001, CR-002, CR-003, and CR-004; update each claim `status` to `decomposed`.
2. In `docs/changes/CHG-001-token-bucket-limiter/change.yaml`, add `TASK-001` and `TASK-002` under `tasks:` with `slice: SLICE-01`, `depends_on: []`, and `requirement_delta: none`.
3. Preserve all other keys and file contents.

## Test oracle

- `coverage.yaml` lists `TASK-001` under every claim and no claim is left with an empty `tasks` array.
- `change.yaml` `tasks` contains both task IDs with valid schema fields.

## Unchanged behavior

- Do not alter spec files, slices, routing, or the spec-delta.

## Allowed / forbidden

- Allowed: `docs/changes/CHG-001-token-bucket-limiter/coverage.yaml`, `docs/changes/CHG-001-token-bucket-limiter/change.yaml`.
- Forbidden: `docs/spec/`, production `src/`, and any other path.

## Verification

- Validate YAML parses and matches `process/schemas/task.schema.yaml` for the task metadata added to `change.yaml`.
