---
name: decompose
description: Decompose one specified DeltaFuse slice into dependency-ordered atomic task files inside its Change package. Use after the specification gate; do not use to discover requirements.
---

# Decompose

Create executable work without creating new product law.

Resolve artifact roots and context limits from `.deltafuse/config.yaml`; paths shown below are defaults.

## Worker (LLM)

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, and `check-gate`.

1. If no Change was named, run `deltafuse next --step decompose` at the product root and use `path`. Halt if it exits non-zero.
2. Write only this step's artifacts (see Procedure).
3. Close with `deltafuse check-gate <change-dir> --gate decomposed`. Halt if it exits non-zero. Then run `deltafuse advance <change-dir> --gate decomposed` so the Core stamps the transition; halt if that exits non-zero.
4. Then run `deltafuse next`. Do not choose the next slash command yourself. If it names a ready step, load that skill and execute it in this same session. If it exits non-zero with halt.kind `decision` or `spec`, present `halt.choices` in the host multiple-choice UI, wait, run only `choice.command`, and continue. If `check-gate` failed or they chose inspect, stop.
5. Do not auto-accept Decisions or merge.

## Context

Read one specified slice and typed delta, exact accepted spec references, optional `design.md`, capability dependencies, compact code/test index or narrowly selected files, and existing task IDs/dependencies.

Do not read all raw intake, the entire spec/codebase, or unrelated Changes/tasks.

## Procedure

1. Create each task with the Artifact Writer, one call per task: `deltafuse artifact write --kind task --change <change-dir> --input <file.json>` (or the host's `artifact_write` tool with the same fields); put the JSON file under `.deltafuse/tmp/`. The Core writes `id`, `change`, `status`, `context_budget` and the file itself. Never write this file by hand: the leash refuses it. A refused field comes back with its reason - fix that field and call again. The Core also adds the task to `change.yaml`.
2. Give each task one verifiable outcome that fits one implementation context. The input, with ids `TASK-001`, `TASK-002`, … (digits only):

   ```json
   {
     "identity": "TASK-001",
     "fields": {
       "slice": "SLICE-01",
       "title": "One line of the outcome",
       "kind": "feature",
       "depends_on": [],
       "requirement_delta": "added",
       "spec_refs": ["docs/spec/<domain>/<capability>.md#REQ-ID"],
       "design_ref": null,
       "allowed_paths": ["src/<module>.py", "tests/test_<module>.py"],
       "forbidden_paths": []
     },
     "body": "The outcome, the test oracle and the unchanged behaviour, in prose."
   }
   ```

   `kind`: feature | bugfix | refactor | maintenance | documentation. `requirement_delta`: none | added | modified | removed | mixed. `forbidden_paths` narrows the task's product scope; on the `code` route never forbid `tests/**` - declare writes the Red test there.
3. To change a task, call `artifact write` again with the same `identity` and only the fields that change.
4. Order `depends_on`. The Core derives `coverage.yaml` (`deltafuse coverage`).
5. For an implementation bug, derive tasks from observation, reproduction, exact existing spec refs, oracle, unchanged behavior, and scope with `requirement_delta: none`.

Do not copy normative spec text, hide a design choice inside a task, estimate primarily by lines of code, or modify production code.

## Gate

Every slice requirement is covered by a resolvable task, every task has a test oracle and `context_budget`, spec and blocking Decisions are accepted, and scope has not expanded. Declared `allowed_paths` must stay inside Declare/Implement write globs for the Change `route` (`code` default: tests/src; `docs`: `docs/spec/**` and `CHANGELOG.md`; `ops`: `deploy/**`, `docs/ops/**`, `ops/**`). `docs`/`ops` must not list `src/**` or `tests/**`. Exceeding the budget fails `decomposed`.
