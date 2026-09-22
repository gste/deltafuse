---
name: verify
description: Verify traceability and cross-artifact convergence for a DeltaFuse Change, then archive its complete package. Use after all tasks are implemented or for an explicit no-op/not-reproduced closure.
---

# Verify

Prove that the Delta was fully fused before removing the Change from active context.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Worker (LLM)

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, and `check-gate`.

1. If no Change was named, run `deltafuse next --step verify` at the product root and use `path`. Halt if it exits non-zero.
2. Write only this step's artifacts (see Procedure).
3. Close with `deltafuse check-gate <change-dir> --gate converged`. Halt if it exits non-zero.
4. After the gate passes, archive with `deltafuse archive <change-dir>`. Then run `deltafuse next`. Do not choose the next slash command yourself. If it names a ready step, load that skill and execute it in this same session. If it exits non-zero with halt.kind `decision` or `spec`, present `halt.choices` in the host multiple-choice UI, wait, run only `choice.command`, and continue. If they chose inspect, or there is no new intake, stop. Merge/push is a Human Gate. Do not git push.
5. Do not auto-accept Decisions or merge.

## Context

Read Change/slice summaries, coverage, terminal task states, exact spec references, test evidence, code/spec diffs, and Decision statuses. Deepen into source artifacts only for a detected gap.

## Procedure

1. Verify `raw source -> CR claim -> analysis -> slice Delta -> requirement -> task -> test -> result` coverage.
2. Check every declared delta projection and unchanged invariant.
3. Confirm blocking Decisions are terminal and accepted normative consequences exist in spec.
4. Confirm valid Red/Green evidence, scoped regressions, allowed paths, and no test-oracle weakening.
5. Record the Change-level run - the `converged` gate requires it: `deltafuse evidence <change-dir> --phase verification -- <full test command>` writes `evidence/verification/run.yaml` with the current `docs/spec/**` and `src/**` tree. The Core maps every claim to its tasks and their evidence in `coverage.yaml` itself when it closes the `converged` gate; do not write that mapping by hand.
6. The `converged` gate checks that `spec-delta.md` `added`/`modified` paths still exist under `docs/spec/**` and that `removed` paths are gone; do not treat archive as a spec merge.
7. Write `verification.md` with `converged` or an exact gap: `tasks-missing`, `spec-gap`, `test-gap`, `scope-drift`, `decision-gap`, or `not-reproduced`. Record `deltafuse state <change-dir> --task <task-id> --status verified` for each implemented task. Leave `cancelled` / `superseded` tasks in those terminal statuses; do not fake `implemented`.
8. For a gap, stop; do not repair it silently.
9. After `deltafuse check-gate <change-dir> --gate converged` passes, run `deltafuse advance <change-dir> --gate converged`, then archive with `deltafuse archive <change-dir>`. Do not invent a second archive process.

Archive is provenance, not default implementation context. Do not delete completed task history.

For `route: docs` or `ops`, Verify is spec/file traceability without product pytest; the hidden code suite does not apply. Specify still does not write deploy YAML.
