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
3. Close with `deltafuse check-gate <change-dir> --gate decomposed`. Halt if it exits non-zero.
4. Then run `deltafuse next`. Do not choose the next slash command yourself. If it names a ready step, load that skill and execute it in this same session. If it exits non-zero with halt.kind `decision` or `spec`, present `halt.choices` in the host multiple-choice UI, wait, run only `choice.command`, and continue. If `check-gate` failed or they chose inspect, stop.
5. Do not auto-accept Decisions or merge.

## Context

Read one specified slice and typed delta, exact accepted spec references, optional `design.md`, capability dependencies, compact code/test index or narrowly selected files, and existing task IDs/dependencies.

Do not read all raw intake, the entire spec/codebase, or unrelated Changes/tasks.

## Procedure

1. Create `docs/changes/<change-id>/tasks/TASK-NNN.md` files (optional `TASK-NNN-<slug>.md` filename). Frontmatter `id` is `TASK-001` (digits only, no slug). Status `pending`, not `proposed`.
2. Give each task one verifiable outcome that fits one implementation context.
3. Copy the task template frontmatter: `kind`, `depends_on` (not `dependencies`), `requirement_delta: added` (not `add`), `spec_refs`, `allowed_paths`, `forbidden_paths`, `context_budget`. No `title` or `claims` in frontmatter. In `change.yaml`, `tasks` is a list of strings (`TASK-001`), not objects.
4. Order `depends_on` and update `coverage.yaml` plus the `tasks` string list in `change.yaml`.
5. For an implementation bug, derive tasks from observation, reproduction, exact existing spec refs, oracle, unchanged behavior, and scope with `requirement_delta: none`.

Do not copy normative spec text, hide a design choice inside a task, estimate primarily by lines of code, or modify production code.

## Gate

Every slice requirement is covered by a resolvable task, every task has a test oracle and `context_budget`, spec and blocking Decisions are accepted, and scope has not expanded. Declared `allowed_paths` must stay inside Declare/Implement write globs for the Change `route` (`code` default: tests/src; `docs`: `docs/spec/**` and `CHANGELOG.md`; `ops`: `deploy/**`, `docs/ops/**`, `ops/**`). `docs`/`ops` must not list `src/**` or `tests/**`. Exceeding the budget fails `decomposed`.
