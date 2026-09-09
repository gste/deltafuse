# Board snapshot contract (DeltaFuse ↔ fuse-map)

[**English**](board-snapshot.md) | [Русский](board-snapshot.ru.md)

Machine schema: [board-snapshot.schema.yaml](board-snapshot.schema.yaml) (`schema_version: 1`).

This is the **producer-canonical** contract. The fuse-map repository pins the same `schema_version` under `docs/contracts/`. Artifact SSOT remains the product git tree. This snapshot is a read-only projection.

Implementation of the CLI/API is [FM-001](../../backlog/product/FM-001.md) (separate branch). Shipping the command is not required for this document to be the compatibility pin.

## Roles

| Party | Repository | Duty |
|---|---|---|
| Producer | DeltaFuse | Emit a snapshot that validates against this schema. Never write product files while building it. |
| Consumer | fuse-map | Render cards from the snapshot only. Never treat fuse-map storage as Change SSOT. |
| Store | Product git | Owns `docs/changes/**`, archive, spec, Decisions. |

A directory is a DeltaFuse product iff `.deltafuse/lock.yaml` exists and is readable. No lock → hard error, not an empty board.

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

The same object is the return value of a Python function (name left to FM-001). fuse-map SHOULD call the library when it shares a Python env; CLI is the language-neutral pin.

## Compatibility

`schema_version` is **not** `change.yaml` `schema_version` (that stays `2`).

| Change | What to do |
|---|---|
| Add optional property | Keep `schema_version: 1`. Producer MAY add. Consumer MUST ignore unknown keys. |
| Rename, remove, change type, or change meaning of a required field | Producer MUST bump `schema_version` to `2`. |
| Consumer sees unknown `schema_version` | MUST fail that repo visibly. MUST NOT guess layout by scanning YAML. |
| Consumer sees v1 | MUST accept; MUST NOT require fields that v1 marks optional. |

Both repos keep a copy of `board-snapshot.schema.yaml` for v1. After a bump, DeltaFuse updates canonical schema first; fuse-map updates its pin in the same compatibility change (or explicitly documents a lag and refuses newer versions).

## Consumer MUST NOT

- Parse `docs/changes/*/change.yaml` as the compatibility contract once `board` exists.
- Write `change.yaml`, archive a Change, accept a Decision, or invoke lifecycle skills.
- Hide producer `warnings` or CLI errors to keep columns green.
- Store card bodies (spec, request, evidence) in fuse-map as SSOT.

fuse-map MAY persist only local product root paths in **its own** user config.

## Producer MUST NOT

- Put `docs/spec/**` or `request.md` bodies in the snapshot.
- Invent a product-side index file for the board.
- Expose hidden-suite results or auto-accept Decisions through this API.
- Serve the snapshot as an HTTP daemon in v1 (stdout/library is enough).

## Example (`schema_version: 1`)

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-09T16:00:00Z",
  "product": {
    "baseline": "accepted",
    "framework_version": "2.0.0",
    "framework_content_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "call_width": "wide",
    "changes_path": "docs/changes",
    "archive_changes_path": "docs/archive/changes"
  },
  "changes": [
    {
      "id": "CHG-001-example",
      "title": "Example",
      "status": "analyzed",
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
