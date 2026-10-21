---
name: verify
description: Verify traceability and cross-artifact convergence for a DeltaFuse Change, then archive its complete package. Use after all tasks are implemented or for an explicit no-op/not-reproduced closure.
---

# Verify

Prove that the Delta was fully fused before removing the Change from active context.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Worker (LLM)

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, and `advance`.

1. If no Change was named, run `deltafuse next --step verify` at the product root and use `path`. Halt if it exits non-zero.
2. Write only this step's artifacts (see Procedure).
3. Close with `deltafuse advance <change-dir> --gate converged`: the Core checks the gate and stamps the transition in one call. Halt if it exits non-zero and show the errors it prints.
4. Archive with `deltafuse archive <change-dir>` only after that stamp succeeded, because archive applies only from status `converged`. Then run `deltafuse next`. Do not choose the next slash command yourself. If it names a ready step, load that skill and execute it in this same session. If it exits non-zero with halt.kind `decision` or `spec`, present `halt.choices` in the host multiple-choice UI, wait, run only `choice.command`, and continue. If they chose inspect, or there is no new intake, stop. Merge/push is a Human Gate. Do not git push.
5. Do not auto-accept Decisions or merge.

## Context

Read `coverage.yaml`: the Core's map of every claim to its slice, tasks and evidence records, and `task_evidence` - per task, what its Red, Green and regression records say as the Core judged them (status, result, current tree or stale, and `problems`). Also read `spec-delta.md`, slice summaries, exact spec references and Decision statuses. Open an evidence record, a task file or a source artifact only when a gate error or a `problems` entry names it, or for a gap you found.

## Procedure

1. Verify `raw source -> CR claim -> analysis -> slice Delta -> requirement -> task -> test -> result` coverage from `coverage.yaml`: every claim has a slice, a task and evidence paths. When `workflow.trace_claims: warn` is set, `advance --gate converged` prints every Expectation/Constraint claim `coverage.yaml` has no test for; read that list and check it by hand - it is advisory, not a gate failure.
2. Check every declared delta projection and unchanged invariant.
3. Confirm blocking Decisions are terminal and accepted normative consequences exist in spec.
4. Take Red/Green/regression evidence, allowed paths and the frozen oracle from `task_evidence` in `coverage.yaml`; do not open each record to check it again.
5. Record the Change-level run - the `converged` gate requires it: `deltafuse evidence <change-dir> --phase verification -- <full test command>` writes `evidence/verification/run.yaml` with the current `docs/spec/**` and `src/**` tree. The full test command runs the whole suite, not a chosen part of it: the gate refuses a run that did not pass every test the Change's Red and regression records name. A test that still fails is fixed, never left out of the command. A run that ran no test is refused; with Gradle add `--rerun`. Do not write the claim-to-evidence mapping in `coverage.yaml` by hand: the Core writes it.
6. The `converged` gate checks that `spec-delta.md` `added`/`modified` paths still exist under `docs/spec/**` and that `removed` paths are gone; do not treat archive as a spec merge.
7. Write `verification.md` with a `- Outcome:` line holding exactly one verdict: `converged`, or an exact gap - `tasks-missing`, `spec-gap`, `test-gap`, `scope-drift`, `decision-gap`, `not-reproduced`. The `converged` gate reads that line, so a gap verdict refuses the gate; the template's placeholder line is not a verdict. Record `deltafuse state <change-dir> --task <task-id> --status verified` for each implemented task. Leave `cancelled` / `superseded` tasks in those terminal statuses; do not fake `implemented`.
8. For a gap, stop; do not repair it silently. `deltafuse next` then halts for the human; for `spec-gap` the human may reopen the Change for Analyze (`deltafuse decide <change-dir> --gap spec-gap --status reopened`), so name in `verification.md` exactly what the specification lacks and which file holds it.
9. Do not invent a second archive process.

Archive is provenance, not default implementation context. Do not delete completed task history.

For `route: docs` or `ops`, Verify is spec/file traceability without product pytest.
