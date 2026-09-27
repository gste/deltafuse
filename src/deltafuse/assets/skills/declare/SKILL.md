---
name: declare
description: Declare what must become true for one DeltaFuse task by writing a Red oracle that fails on unchanged production code. Use before /implement.
---

# Declare

Declare the behavior that must become true. That is the point of writing Red tests before Implement.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Worker (LLM)

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, and `check-gate`.

1. If no Change or task was named, run `deltafuse next --step declare` at the product root and use `path` / `task_path`. Halt if it exits non-zero.
2. Write only this step's artifacts (see Procedure). Record Red with `deltafuse evidence`, not by hand-writing YAML.
3. The `declaring` gate covers every task of the Change, so do not check it after each task: while `deltafuse next` names another task, declare that one (each task records its own state, Procedure step 7). When `next` says to close the declaring gate, close with `deltafuse check-gate <change-dir> --gate declaring`. Halt if it exits non-zero. Then run `deltafuse advance <change-dir> --gate declaring` so the Core stamps the transition; halt if that exits non-zero.
4. Then run `deltafuse next`. Do not choose the next slash command yourself. If it names a ready step, load that skill and execute it in this same session. If it exits non-zero with halt.kind `decision` or `spec`, present `halt.choices` in the host multiple-choice UI, wait, run only `choice.command`, and continue. If `check-gate` failed or they chose inspect, stop.
5. Do not auto-accept Decisions or merge.

## Context

Read one task, exact spec references, reproduction and unchanged behavior, relevant test conventions/fixtures/helpers, and only public product interfaces needed to express the oracle.

Do not read implementation internals unless the oracle cannot otherwise be expressed. Do not change production code, specification, Decisions, or the task's expected behavior.

## Procedure

1. Confirm task dependencies and normative references are ready.
2. Freeze the declared oracle from the task and specification: what must become true.
3. Add or modify the smallest automated test that demonstrates the missing behavior or defect. Name the claim it proves: put the claim id in the test's own name (`test_cr013_...`), or add a `# covers: CR-013` comment inside it when the name cannot. `deltafuse coverage` reads this to record which claim each test proves; a claim with none is named at `check-gate --gate converged` when `workflow.trace_claims: warn` is set (off by default).
4. Run that test against unchanged production code by calling the kernel, not by hand-writing YAML:
   `deltafuse evidence <change-dir> --phase red --task <task-id> -- <command>`. The Core records the changed files itself (`--changed-path` is optional).
5. Authentic Red is two exit codes at once: the test command exits non-zero because the behavior is missing, and `deltafuse evidence` exits 0 because it recorded that failure as `failure_category: behavioral-mismatch`. A test that could not run - compilation, import, collection, fixture, environment, or `_`-prefixed internals - is not Red; the kernel still writes the YAML, but `deltafuse evidence` exits non-zero and the gate does not pass.
   On a compiled language the test cannot reference what does not exist yet: add the signature first (a stub that throws), then take Red against it. The stub is production scope, so it must already be listed in this task's `allowed_paths` - Decompose declares it, Declare cannot (`tasks/**` is outside this step's write scope). If it is not listed, stop and return the task upstream; do not write the stub anyway.
6. `changed_paths` must stay inside the Declare write scope (`tests/**`, Red evidence) plus the product paths this task's `allowed_paths` declares - on a compiled language that is the stub and nothing else. Every other production `src/**` path is written in Implement, after Red is recorded.
7. Record the Core-owned task state: `deltafuse state <change-dir> --task <task-id> --status declared` (only after valid Red). Never set task or Change status by hand.

If already Green, invalid, environment-blocked, or not reproduced, stop and return that outcome upstream. Record `already-green` when the public oracle already passes. Do not access `_`-prefixed product internals to manufacture Red. Do not weaken assertions to manufacture Red.

For `route: docs` or `ops`, record a file or schema oracle in `evidence/red/` instead of product pytest; do not list `src/**` or `tests/**`. Hidden code-suite checks do not apply.

Optional: add Hypothesis-class property tests as extra oracles for an invariant. Skip if no local runner. PBT does not replace the GWT example Red test or the independent hidden suite. Do not add `.kiro` or Cucumber as Declare.
