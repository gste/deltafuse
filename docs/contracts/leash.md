# Write envelope (DeltaFuse ↔ leash / host)

[**English**](leash.md) | [Русский](leash.ru.md)

Machine schema: [leash.schema.yaml](leash.schema.yaml) (contract v1).

This is the **producer-canonical** write envelope. `deltafuse leash`, a git hook, or a host pins the same schema. It is not a product artifact schema; the installer must not copy `docs/contracts/**` into a product.

Producer: `deltafuse next --json` (`deltafuse.core.leash.build_envelope` via `queue_snapshot`). Guard: `deltafuse leash`. Core does not draw UI and does not `git push`.

`envelope` is either an object that validates against this schema, or JSON `null`. `null` means there is no ready Worker step (Human Gate, blocked, or `halt.kind: done`). Code/ops/deploy paths in the diff with a null envelope are **orphans**: `deltafuse leash` MUST fail (unless `advisory`). `docs/spec/**` is an orphan only after `project.baseline: accepted`. `docs/intake/**`, `AGENTS.md`, and `.deltafuse/lock.yaml` are not orphans.

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
| Human Gate / nothing to run | `envelope` is JSON `null`. Product paths in the diff are orphans and fail. Exempt paths (`docs/intake/**`, `AGENTS.md`, `.deltafuse/**`) still skip. |
| Orphan product edit | `src/**`, `tests/**`, ops/deploy MUST be covered by a ready Change envelope. `docs/spec/**` MUST after `project.baseline: accepted`. Docs/ops route MUST NOT cover `src/**`. |
| Intake `write` | MUST NOT include `src/**`. |
| Declare/Implement | Declare keeps `tests/**` and Red evidence globs, not `src/**`. Implement keeps `tests/**` and shrinks product paths to task `allowed_paths`. |
| `leash` side effects | Zero product writes. Diagnostics on stderr unless `--json`. |
| `workflow.leash` | Fresh `init` writes `off` (no hook). `advisory`: same violations, exit `0` (hook does not block commit). Missing/`enforce`: exit `≠ 0` when a path is outside `write`. `enforce` and `advisory` install a local `pre-commit` that runs `deltafuse leash`. The hook MUST NOT `git push`. |

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
