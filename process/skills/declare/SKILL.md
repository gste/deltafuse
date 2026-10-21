---
name: declare
description: Declare what must become true for one DeltaFuse task by writing a Red oracle that fails on unchanged production code. Use before /implement.
---

# Declare

Declare the behavior that must become true. That is the point of writing Red tests before Implement.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Worker (LLM)

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, and `advance`.

1. If no Change or task was named, run `deltafuse next --step declare` at the product root and use `path` / `task_path`. Halt if it exits non-zero.
2. Write only this step's artifacts (see Procedure).
3. The `declaring` gate covers every task of the Change, so do not check it after each task: while `deltafuse next` names another task, declare that one (each task records its own state, Procedure step 7). When `next` says to close the declaring gate, close with `deltafuse advance <change-dir> --gate declaring`: the Core checks the gate and stamps the transition in one call. Halt if it exits non-zero and show the errors it prints.
4. Then run `deltafuse next`. Do not choose the next slash command yourself. If it names a ready step, load that skill and execute it in this same session. If it exits non-zero with halt.kind `decision` or `spec`, present `halt.choices` in the host multiple-choice UI, wait, run only `choice.command`, and continue. If `advance` failed or they chose inspect, stop.
5. Do not auto-accept Decisions or merge.

## Context

Read one task, exact spec references, reproduction and unchanged behavior, relevant test conventions/fixtures/helpers, and only public product interfaces needed to express the oracle.

Do not read implementation internals unless the oracle cannot otherwise be expressed. Do not change production code, specification, Decisions, or the task's expected behavior.

## Procedure

1. Confirm task dependencies and normative references are ready.
2. Freeze the declared oracle from the task and specification: what must become true.
3. Add or modify the smallest automated test that demonstrates the missing behavior or defect. Name the claim it proves: put the claim id in the test's own name (`test_cr013_...`), or add a `# covers: CR-013` comment inside it when the name cannot.
4. Run that test against unchanged production code by calling the kernel, not by hand-writing YAML:
   `deltafuse evidence <change-dir> --phase red --task <task-id> -- <command>`. The Core records the changed files itself (`--changed-path` is optional).
5. Authentic Red is two exit codes at once: the test command exits non-zero because the behavior is missing, and `deltafuse evidence` exits 0 because it recorded that failure as `failure_category: behavioral-mismatch`. A test that could not run - compilation, import, collection, fixture, environment, or `_`-prefixed internals - is not Red: `deltafuse evidence` exits non-zero and the gate does not pass. Each Red test must fail because the behavior is missing, not on an error in its own code (a name it never bound, an operator between built-in values on a line that uses nothing from the product): `deltafuse evidence` refuses such a Red and names the test and line - fix the test.
6. `changed_paths` must stay inside the Declare write scope (`tests/**`, Red evidence) plus the product paths this task's `allowed_paths` declares. On a compiled language the test cannot reference what does not exist yet: add the signature first (a stub that throws), then take Red against it - the stub is the only product file Declare writes, and it must already be in `allowed_paths` (Decompose declares it; Declare cannot write `tasks/**`); if it is not, stop and return the task upstream. Every other production `src/**` path is written in Implement, after Red is recorded.
7. Record the Core-owned task state: `deltafuse state <change-dir> --task <task-id> --status declared` (only after valid Red). Never set task or Change status by hand.

If invalid, environment-blocked, or not reproduced, stop and return that outcome upstream. If the public oracle already passes, record it as Red anyway (`deltafuse evidence` writes `already-green`): for a task with `requirement_delta: none` earlier work already meets it, so close it with `deltafuse state <change-dir> --task <task-id> --status superseded` - its test stays as regression; for a task that promises a requirement delta, stop and report it, the human settles it. Never proceed to Implement on an already-green Red. Do not access `_`-prefixed product internals or weaken assertions to manufacture Red. A test another task's Red froze is that task's oracle: leave it as frozen and write a new test. A task the human reopened (the `next` reason names `reopened/<task>.<n>/` and the human's note) has its product files back as the `declaring` gate found them: correct the oracle only where it contradicts the accepted specification or itself - not to suit the current code - and record Red against them.

For `route: docs` or `ops`, record a file or schema oracle in `evidence/red/` instead of product pytest; do not list `src/**` or `tests/**`.

Optional: add Hypothesis-class property tests as extra oracles for an invariant. Skip if no local runner. PBT does not replace the GWT example Red test or the independent hidden suite. Do not add `.kiro` or Cucumber as Declare.
