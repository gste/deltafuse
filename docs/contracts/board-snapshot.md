# Board snapshot contract (DeltaFuse ↔ fuse-map)

[**English**](board-snapshot.md) | [Русский](board-snapshot.ru.md)

Machine schema: [board-snapshot.schema.yaml](board-snapshot.schema.yaml) (`schema_version: 1`).

This is the **producer-canonical** contract. The fuse-map repository pins the same `schema_version` under `docs/contracts/`. Artifact SSOT remains the product git tree. This snapshot is a read-only projection.

Producer command: `deltafuse board`. Python: `deltafuse.core.board.build_board_snapshot`.

`layout` is required on v1. No producer has shipped yet; this completes v1 rather than bumping to 2. A body without `layout` is not a valid snapshot.

## Roles

| Party | Repository | Duty |
|---|---|---|
| Producer | DeltaFuse | Emit a snapshot that validates against this schema. Never write product files while building it. Own lifecycle geometry (`layout`) and card projection (`changes`). |
| Consumer | fuse-map | Render only what the snapshot contains. Stateless: no card store, no persisted roots, no hardcoded columns or steps. |
| Store | Product git | Owns `docs/changes/**`, archive, spec, Decisions. |

A directory is a DeltaFuse product iff `.deltafuse/lock.yaml` exists and is readable. No lock → hard error, not an empty board.

## What fuse-map is allowed to know

The consumer is a projector. Per invocation it receives product root path(s) as arguments and one snapshot per root. It MUST NOT keep a second copy of cards, layout, or roots after the process exits.

| Need | Source | Not a source |
|---|---|---|
| Column list and order | `layout.columns` | `docs/state-machine.md`, fuse-map source, user config |
| Which statuses sit in a column | `layout.columns[].statuses` | Hardcoded folding tables |
| Step list and which columns they join | `layout.steps` | Skill folder names in the UI repo |
| Cards | `changes` (and `archive` only if requested) | `docs/changes/**` parsed by the UI |
| Where to open a Change | `card.path` + the invocation's product root | Guessed `docs/changes/<id>` |

### Placement rule

For each card in `changes`, find the unique column where `card.status` is listed in `column.statuses`. Put the card there. If no column lists that status, omit the card from the default board (terminals such as `rejected` / `archived` MUST NOT appear in any happy-path column). If two columns list the same status, the snapshot is invalid; the producer MUST NOT emit it.

Display title for a column or step: `label` if present, otherwise `id`.

`layout.steps` are legend only. `from` / `to` are column ids. A step with only `to` is an entry (intake). A step with only `from` is an exit (archive). The consumer MUST NOT treat a step as a command to run a skill.

## Transport

```text
deltafuse board <product-root> --json
deltafuse board <product-root> --json --archive
```

| Rule | MUST |
|---|---|
| `--json` | The **only** stdout content is one JSON object (UTF-8). Diagnostics go to stderr. |
| Success | Exit `0`, body validates against this schema. |
| Not a product / unreadable lock or config | Exit `≠ 0`, no partial JSON pretending to be a board. |
| `--archive` | Include `archive` array; omit the key when the flag is absent. |
| Paths | Resolve Change roots from `.deltafuse/config.yaml` `paths.changes` and `paths.archive`, not hardcoded `docs/changes`. |
| Side effects | Zero file creates/updates/deletes under `<product-root>`. |
| Gate fan-out | Must not run `check-gate` on every Change by default. Optional later flag, not v1. |
| Layout | `layout` is framework geometry for the pinned DeltaFuse version. It MUST NOT depend on which Changes exist. Empty `changes` still includes the full `layout`. |

The same object is the return value of a Python function (name left to FM-001). fuse-map SHOULD call the library when it shares a Python env; CLI is the language-neutral pin.

## Compatibility

`schema_version` is **not** `change.yaml` `schema_version` (that stays `2`).

| Change | What to do |
|---|---|
| Add optional property | Keep `schema_version: 1`. Producer MAY add. Consumer MUST ignore unknown keys. |
| Rename, remove, change type, or change meaning of a required field | Producer MUST bump `schema_version` to `2`. |
| Consumer sees unknown `schema_version` | MUST fail that repo visibly. MUST NOT guess layout by scanning YAML. |
| Consumer sees v1 | MUST accept; MUST NOT require fields that v1 marks optional. MUST require `layout`. |
| `card.status` | Opaque string. Consumer MUST NOT keep a private enum of statuses. |

Both repos keep a copy of `board-snapshot.schema.yaml` for v1. After a bump, DeltaFuse updates canonical schema first; fuse-map updates its pin in the same compatibility change (or explicitly documents a lag and refuses newer versions).

## Consumer MUST NOT

- Parse `docs/changes/*/change.yaml` as the compatibility contract once `board` exists.
- Hardcode column ids, step ids, or status-to-column maps.
- Persist product roots, cards, or layout in fuse-map user config or a database.
- Write `change.yaml`, archive a Change, accept a Decision, or invoke lifecycle skills.
- Hide producer `warnings` or CLI errors to keep columns green.
- Store card bodies (spec, request, evidence) in fuse-map as SSOT.

Product roots are invocation inputs only.

## Producer MUST NOT

- Put `docs/spec/**` or `request.md` bodies in the snapshot.
- Invent a product-side index file for the board.
- Expose hidden-suite results or auto-accept Decisions through this API.
- Serve the snapshot as an HTTP daemon in v1 (stdout/library is enough).
- Omit `layout` or emit a layout that disagrees with the pinned framework lifecycle.

## Example (`schema_version: 1`)

Values under `layout` are producer-owned. The consumer treats them as data.

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-10T06:00:00Z",
  "product": {
    "baseline": "accepted",
    "framework_version": "2.5.0",
    "framework_content_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "call_width": "wide",
    "changes_path": "docs/changes",
    "archive_changes_path": "docs/archive/changes"
  },
  "layout": {
    "columns": [
      { "id": "normalized", "statuses": ["normalized"] },
      { "id": "analyzed", "statuses": ["analyzing", "blocked-on-decision", "analyzed"] },
      { "id": "specified", "statuses": ["specification-proposed", "specified"] },
      { "id": "decomposed", "statuses": ["decomposed"] },
      { "id": "target-confirmed", "statuses": ["targeting", "target-confirmed"] },
      { "id": "implemented", "statuses": ["implementing", "implemented"] },
      { "id": "converged", "statuses": ["verifying", "converged"] }
    ],
    "steps": [
      { "id": "intake", "to": "normalized" },
      { "id": "analyze", "from": "normalized", "to": "analyzed" },
      { "id": "specify", "from": "analyzed", "to": "specified" },
      { "id": "decompose", "from": "specified", "to": "decomposed" },
      { "id": "declare", "from": "decomposed", "to": "target-confirmed" },
      { "id": "implement", "from": "target-confirmed", "to": "implemented" },
      { "id": "verify", "from": "implemented", "to": "converged" },
      { "id": "archive", "from": "converged" }
    ]
  },
  "changes": [
    {
      "id": "CHG-001-example",
      "title": "Example",
      "status": "analyzing",
      "route": "code",
      "path": "docs/changes/CHG-001-example",
      "blocked_decisions": [],
      "slice_count": 1,
      "task_count": 0,
      "has_red": false,
      "has_green": false
    }
  ],
  "warnings": []
}
```

In this example the card sits in column `analyzed` because `analyzing` is listed there. Fuse-map does not contain that folding table.
