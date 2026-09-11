# Halt contract (DeltaFuse ↔ host)

[**English**](halt.md) | [Русский](halt.ru.md)

Machine schema: [halt.schema.yaml](halt.schema.yaml) (contract v1).

This is the **producer-canonical** host contract. Cursor, an IDE, or any orchestrator pins the same schema. It is not a product artifact schema and the installer must not copy `docs/contracts/**` into a product.

Producer command: `deltafuse next --json`. Python: `deltafuse.core.queue.build_halt` via `queue_snapshot`. Apply a click with `deltafuse decide`. Core does not draw buttons, does not auto-accept, and does not `git push`.

`halt` is either a JSON object that validates against this schema, or JSON `null`. `null` means a ready Worker step is selected: run that skill, no buttons.

## Roles

| Party | Where | Duty |
|---|---|---|
| Producer | DeltaFuse Core | Emit `halt` that validates. Own `kind`, `prompt`, and `choices`. Never include merge/`git push`. |
| Consumer | Host (Cursor, IDE, bot) | Render `choices` as buttons. Wait. Run only `choice.command`. Never let the Worker pick. |
| Worker | LLM or human filling Change files | Stops at a Human Gate. Does not choose `halt.choices`. |
| Store | Product git | Owns Decisions, spec, Change files. `decide` writes the recorded click. |

## Host MUST

| Need | Source | MUST |
|---|---|---|
| Whether to show buttons | `halt` | Object → show buttons. `null` → run `selected`, no buttons. |
| Button list and labels | `halt.choices[].label` | Render every choice. Do not add Merge / Push / Accept-all. |
| What to run on click | `halt.choices[].command` | Non-null: run that string as-is from the product root. `null` (`id: inspect`): stop. Do not call `decide`. |
| Who may click | Human | Wait. Do not let the Worker select a choice from chat. `decide` records the click; it is not auto-accept. |
| Bench pack | Judge host / `--pack` / `DELTAFUSE_BENCH_PACK` | Keep oracle and hidden suite off the Worker sandbox and off generated adapter skills. |
| Board UI | Other repository | Read `deltafuse board --json` ([board-snapshot](board-snapshot.md)). Do not draw a board in this repo. |

## Transport

```text
deltafuse next <product-root> --json
deltafuse decide <change-dir> --decision DEC-0001 --status accepted
deltafuse decide <change-dir> --spec --status accepted
```

| Rule | MUST |
|---|---|
| `--json` | The **only** stdout content is one JSON object (UTF-8). Diagnostics go to stderr. |
| Ready Worker step | Exit `0`, `halt` is `null`, `selected` names the step. |
| Human Gate / empty queue | `halt` validates against this schema. Exit `≠ 0` when `selected` is `null` (blocked). Exit `0` when `selected` is intake with no pending file (`kind: done`). |
| Non-null `command` | Starts with `deltafuse decide `. Host MUST NOT treat `prompt` as a command. |
| `id: inspect` | `command` is JSON `null`. Stop through-mode. |
| Side effects of `next` | Zero product writes. `decide` is the only Core write for a Human Gate click. |
| `check-gate` | `accepted` / `rejected` on a DEC or `spec-delta.md` without a `.deltafuse/gate-journal.jsonl` click MUST fail. Editing markdown is not a click. |

## Compatibility

The parent `next --json` envelope uses `schema_version: 1`. That integer is **not** `change.yaml` `schema_version` (that stays `2`). This halt schema versions independently via `$id` `.../halt/v1`.

| Change | What to do |
|---|---|
| Add optional property on `halt` or a choice | Keep v1. Host MUST ignore unknown keys. |
| Rename, remove, or change meaning of `kind` / `choices` / `command` | Producer MUST bump the halt contract (`v2`). |
| Host sees a `kind` it does not know | MUST fail visibly. MUST NOT guess a click. |
| Host sees `command` that is not `deltafuse decide …` and not `null` | MUST refuse to run it. |

## Consumer MUST NOT

- Let the Worker pick a halt choice.
- Auto-accept Decisions, spec, merge, or `git push`.
- Invent extra buttons (merge, push, skip gate).
- Copy the bench pack (`oracle.yaml`, `hidden_suite`) into the Worker sandbox or adapter skills.
- Parse `docs/changes/**` to build a board; use [board-snapshot](board-snapshot.md).
- Implement fuse-map UI or IDE buttons inside `src/deltafuse/**`.

## Producer MUST NOT

- Emit a choice whose `command` is merge, `git push`, or anything other than `deltafuse decide …` / `null`.
- Auto-accept a Decision or specification.
- Put oracle, hidden-suite results, or spec bodies in `next --json`.
- Draw buttons or a board in Core.

## Example (`kind: decision`)

```json
{
  "kind": "decision",
  "prompt": "A Decision is a Human Gate. Present these choices and wait. Do not pick.",
  "choices": [
    {
      "id": "accept:DEC-0001",
      "label": "Accept DEC-0001: Pick a store",
      "command": "deltafuse decide docs/changes/CHG-001-example --decision DEC-0001 --status accepted"
    },
    {
      "id": "reject:DEC-0001",
      "label": "Reject DEC-0001: Pick a store",
      "command": "deltafuse decide docs/changes/CHG-001-example --decision DEC-0001 --status rejected"
    },
    {
      "id": "inspect",
      "label": "Stop and inspect",
      "command": null
    }
  ]
}
```
