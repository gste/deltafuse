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
| Host | Cursor, IDE, fuse-map | MUST restrict write tools to `envelope.write`. MUST NOT invent extra globs. Fuse-map UI and Cursor buttons live outside `src/deltafuse/**`. |
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
| Halt + envelope | When `halt.kind` is `decision` or `spec`, `envelope` is JSON `null`. Product-code write tools MUST stay off while those buttons are showing. |
| Diff since base | The guard judges the diff since `--base` (default `HEAD`) against the ready envelopes **and** the envelopes of every step each Change worked through since that base, read from the transition receipts. A finished step's writes are not judged against the step after it; a halt stops new work, not the record of work done. Declare/Implement add only the tasks whose file changed since the base. |
| Core journals (DF3-007) | `.deltafuse/transitions.jsonl`, `gate-journal.jsonl` and `journal-head` pass only as Core-shaped appends: existing lines untouched, every transition receipt digest intact and the chain replayable, gate receipts in the current format with the chain and head verified. Anything else fails. `.deltafuse/trusted-keys.yaml` never belongs in a Worker diff. |
| Core status writes | A task or slice file outside the envelope passes only as the rewrite `deltafuse state` makes: an `artifact-status` receipt appended since the base, the status moved from the first receipt's `from` to the last receipt's `to`, the rest of the frontmatter and the body unchanged. The receipt's `path` names the file (it may be `TASK-NNN-<slug>.md`; only a file of that Change's `tasks/` or `slices/` is accepted). Any other edit of that file fails as outside the envelope. |
| Interpreter caches | `*.pyc`, `__pycache__/**` and `.pytest_cache/**` are exempt: running the Red and Green tests writes them, and the Worker cannot avoid it. |
| Task `forbidden_paths` | In Declare and Implement a task's `forbidden_paths` narrow its test and product scope only. The Change's own files (`docs/changes/*/evidence/**`, `coverage.yaml`, `change.yaml`) stay in the envelope: `deltafuse evidence` writes there, and a task forbidding `docs/**` must not turn that into a violation. |

Transition receipt digests are not keyed: the guard proves a journal change has the shape the Core writes, not that the Core wrote it. Human Gate receipts carry provenance once `deltafuse gate-key init` has registered the human's Ed25519 public key: every later gate receipt must verify against it, and the private key lives outside the product.

## Host MUST

| Need | Source | MUST |
|---|---|---|
| Write allow-list | `envelope.write` | Restrict agent write-tools (ApplyPatch, write, edit) to these globs. MUST NOT invent extra globs. |
| Null envelope + `leash: enforce` | `envelope` is JSON `null` | No ready Worker step (Human Gate, blocked, or `halt.kind: done`). MUST NOT enable product globs (`src/**`, `tests/**`, ops/deploy). `docs/spec/**` after `project.baseline: accepted` is the same. Wait / inspect is allowed. |
| Halt + envelope | `halt.kind` `decision` or `spec` | Envelope is null. MUST NOT open product-code writes while the Human Gate buttons are showing. |
| Host cannot cut tools | `/run` | Still run `deltafuse leash` at the product root before leaving the step. That is not a substitute for the git hook. |
| Board / buttons | Other repository | Fuse-map UI and Cursor button chrome live outside `src/deltafuse/**`. Pin this schema there. This repo MUST NOT ship that UI. |

## Host MUST NOT

- Enable write tools outside `envelope.write`.
- Treat a null envelope as "write anything" when `workflow.leash` is `enforce`.
- Auto-accept Decisions, spec, merge, or `git push`.
- Implement a Cursor plugin, MCP write-gate, or fuse-map board inside `src/deltafuse/**`.

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
