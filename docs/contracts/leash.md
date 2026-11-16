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
| Code roots | `src/**` and `tests/**` above stand for the product's code roots: `workflow.code_roots` in `.deltafuse/config.yaml` when set (for example `[svc/src/**]`), else those two. The hook and `deltafuse leash` judge orphan product edits and the Declare/Implement envelopes against the same roots `deltafuse next` puts in `envelope.read` and `envelope.write`. |
| Intake `write` | MUST NOT include `src/**`. |
| Declare/Implement | Declare keeps `tests/**` and Red evidence globs, not `src/**`. Implement keeps `tests/**` and shrinks product paths to task `allowed_paths`. |
| `leash` side effects | Zero product writes. Diagnostics on stderr unless `--json`. |
| `workflow.leash` | Fresh `init` writes `advisory`. `off`: no hook, and `advance` does not check. `advisory`: same violations, exit `0` (hook does not block commit); `deltafuse advance` runs the same check before it writes the receipt and reports the violations without refusing. `enforce`: `advance` refuses a transition while a path is outside the envelope. A product with no git or no commit cannot be judged: `advance` says `checked: false` with the reason and does not block. Missing/`enforce`: exit `≠ 0` when a path is outside `write`. `enforce` and `advisory` install a local `pre-commit` that runs `deltafuse leash`, in git's own hook directory (`core.hooksPath` when it points inside the repository or its git directory; a shared hooks directory outside it gets a message on how to call `.deltafuse/hooks/pre-commit` instead). The hook MUST NOT `git push`. |
| Mode and roots of a verdict | A diff is judged with the mode and code roots of the base's `.deltafuse/config.yaml`; a stricter mode in the judged or working tree applies at once. A commit that relaxes `workflow.leash` or changes `workflow.code_roots` is itself outside every envelope: these are the human's settings, committed on their own. Within a step `advance` keeps the mode the step started with. |
| Halt + envelope | When `halt.kind` is `decision` or `spec`, `envelope` is JSON `null`. Product-code write tools MUST stay off while those buttons are showing. |
| Diff since base | The guard judges the diff since `--base` (default `HEAD`) against the ready envelopes **and** the envelopes of every step each Change worked through since that base, read from the transition receipts. A finished step's writes are not judged against the step after it; a halt stops new work, not the record of work done. Declare/Implement add only the tasks whose file changed since the base, and only for a record `deltafuse evidence` stamped for that Change, task and phase; a declared task's `allowed_paths` are read from the task as declared at the base. |
| What is judged | The `pre-commit` hook judges the staged tree (the index against `HEAD`, bytes read from the index). `deltafuse leash` judges the working tree. `advance` judges the whole step: every non-merge first-parent commit since the commit the step started from (the parent of the commit that recorded the Change's last transition receipt) and the uncommitted diff, so a `git commit --no-verify` does not hide a write. `--base B --head H` (CI) judges `B...H`, from the merge base. Paths are read raw (non-ASCII names) and without rename detection (a move shows its deletion). |
| Core journals (DF3-007) | `.deltafuse/transitions.jsonl`, `gate-journal.jsonl` and `journal-head` pass only as Core-shaped appends: existing lines untouched, every transition receipt digest intact and the chain replayable, gate receipts in the current format with the chain and head verified. Anything else fails. `.deltafuse/gate-password.yaml` (the Human Gate password hash) never belongs in a Worker diff. `.deltafuse/bench.yaml` is guarded the same way: it holds the `seed_hashes` a bench run scores `code.untouched` from, so it is written by the harness that initialized the product and by nobody else - a Worker that rewrote those digests would erase its own premature `src/**` edits. |
| Core status writes | A task or slice file outside the envelope passes only as the rewrite `deltafuse state` makes: an `artifact-status` receipt appended since the base, the status moved from the first receipt's `from` to the last receipt's `to`, the rest of the frontmatter and the body unchanged. The receipt's `path` names the file (it may be `TASK-NNN-<slug>.md`; only a file of that Change's `tasks/` or `slices/` is accepted). Any other edit of that file fails as outside the envelope. |
| Structural artifacts | `routing.yaml`, `spec-delta.md`, `slices/*.md` and `tasks/*.md` of a Change pass, even inside the envelope, only when their bytes match a known writer's digest: the Artifact Writer's receipt (`result_sha256` in `.deltafuse/receipts/`), `deltafuse state` (`sha256` in its artifact-status receipt) or `decide` (`artifact_sha256` in the gate journal). A hand-written file fails with the `deltafuse artifact write` command to use (roadmap item 1). |
| Human decisions | What `deltafuse decide` writes when the human cancels or reopens a task or reopens a Verify gap passes before anyone commits it, judged by bytes: a file whose bytes a `decide` receipt in the gate journal vouches for (`kind: task` or `gap`); a deleted evidence record whose bytes at the base lie in its own archived copy (the same relative path under the reopen archive) with its receipt; a product file a task reopen restored, when its bytes are the `declaring` snapshot's for that path. The `gap-reopen` entry of `transitions.jsonl` is a Core receipt. Any other bytes are judged as before. `decide` still says to commit these changes before the next step. |
| Interpreter caches | `*.pyc`, `__pycache__/**` and `.pytest_cache/**` are exempt: running the Red and Green tests writes them, and the Worker cannot avoid it. |
| Task `forbidden_paths` | In Declare and Implement a task's `forbidden_paths` narrow its test and product scope only. The Change's own files (`docs/changes/*/evidence/**`, `coverage.yaml`, `change.yaml`) stay in the envelope: `deltafuse evidence` writes there, and a task forbidding `docs/**` must not turn that into a violation. |

Receipt digests are not keyed: the guard proves a journal change has the shape the Core writes, not that the Core wrote it. The same holds for Artifact Writer receipts in `.deltafuse/receipts/`: a hand-made receipt can vouch for a hand-written structural artifact. A clean `git merge` runs no `pre-commit` hook, so what a merge brings in is judged by the CI leash job, not locally. See [What the Core does not stop](../core-and-worker.md#what-the-core-does-not-stop). Provenance needs a channel the Worker cannot reach: host isolation. The optional Human Gate password guards the `decide` command only; see the roadmap, item 4.

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
