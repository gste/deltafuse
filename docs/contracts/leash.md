# Write envelope (DeltaFuse ↔ leash / host)

[**English**](leash.md) | [Русский](leash.ru.md)

Machine schema: [leash.schema.yaml](leash.schema.yaml) (contract v1).

This is the **producer-canonical** write envelope. `deltafuse leash`, a git hook, or a host pins the same schema. It is not a product artifact schema; the installer must not copy `docs/contracts/**` into a product.

Producer: `deltafuse next --json` (`deltafuse.core.leash.build_envelope` via `queue_snapshot`). Guard: `deltafuse leash`. Core does not draw UI and does not `git push`.

`envelope` is either an object that validates against this schema, or JSON `null`. `null` means there is no ready Worker step (Human Gate, blocked, or `halt.kind: done`). `deltafuse leash` does **not** treat a null envelope as an orphan-product failure; that is a later leash rule.

## Roles

| Party | Where | Duty |
|---|---|---|
| Producer | DeltaFuse Core | Emit `envelope` that validates when a Worker step is selected. Own `write[]`. |
| Guard | `deltafuse leash` | Compare git diff (or `--file`) to `envelope.write`. No product writes. |
| Host | Cursor, IDE, fuse-map | MAY restrict write tools to `envelope.write`. MUST NOT invent extra globs. |
| Worker | LLM or human | Write only inside `write[]`. Does not choose the envelope. |

## Transport

```text
deltafuse next <product-root> --json
deltafuse leash <product-root>
deltafuse leash <product-root> --file src/foo.py --file docs/changes/CHG-001/request.md
```

| Rule | MUST |
|---|---|
| Ready Worker step | `halt` is JSON `null`, `envelope` validates, `write` is non-empty. |
| Human Gate / nothing to run | `envelope` is JSON `null`. `leash` exits `0` with `skipped` (no LS-002 judgement). |
| Intake `write` | MUST NOT include `src/**`. |
| Declare/Implement | Declare keeps `tests/**` and Red evidence globs, not `src/**`. Implement keeps `tests/**` and shrinks product paths to task `allowed_paths`. |
| `leash` side effects | Zero product writes. Diagnostics on stderr unless `--json`. |
| `workflow.leash: advisory` | Same violations, exit `0`. Missing/`enforce`: exit `≠ 0` when a path is outside `write`. |

## Example (Analyze)

```json
{
  "step": "analyze",
  "change": "CHG-001-example",
  "task": null,
  "write": [
    "docs/changes/*/routing.yaml",
    "docs/changes/*/analysis.md",
    "docs/changes/*/slices/**",
    "docs/changes/*/coverage.yaml",
    "docs/changes/*/change.yaml"
  ],
  "read": [
    "docs/changes/*/request.md",
    "docs/changes/*/change.yaml",
    "docs/spec/**",
    "docs/decisions/**",
    ".deltafuse/**"
  ]
}
```
