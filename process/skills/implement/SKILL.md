---
name: implement
description: Implement one DeltaFuse task against accepted specification and a frozen declared Red oracle, then record Green evidence. Use only after /declare has confirmed Red.
---

# Implement

Make one declared Red oracle Green with the smallest compliant production change.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Worker (LLM)

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, and `check-gate`.

1. If no Change or task was named, run `deltafuse next --step implement` at the product root and use `path` / `task_path`. Halt if it exits non-zero.
2. Write only this step's artifacts (see Procedure). Record Green and regression with `deltafuse evidence`, not by hand-writing YAML.
3. Close with `deltafuse check-gate <change-dir> --gate implemented`. Halt if it exits non-zero.
4. Then run `deltafuse next`. Do not choose the next slash command yourself. If it names a ready step, load that skill and execute it in this same session. If it exits non-zero with halt.kind `decision` or `spec`, present `halt.choices` in the host multiple-choice UI, wait, run the matching `deltafuse decide` command, and continue. If `check-gate` failed or they chose inspect, stop.
5. Do not auto-accept Decisions or merge.

## Context

Read one task, exact spec references, frozen target test, Red evidence, allowed production files/symbols, and only required local dependencies.

Do not change specification, Decisions, task scope, target oracle/assertions, or unrelated code.

## Procedure

1. Verify the task is `target-confirmed` and Red evidence matches the frozen target.
2. Implement the minimum production change inside allowed scope.
3. Record Green with the kernel, not by hand-writing YAML:
   `deltafuse evidence <change-dir> --phase green --task <task-id> --changed-path <rel> -- <target-command>`.
4. Record scoped regression the same way (`--phase regression`). The runner fills `exit_code`, `failure_category`, and `base_revision`.
5. `changed_paths` must stay inside `PHASE_CONTRACTS` Implement write scope and outside the task `forbidden_paths`. CLI exit 0 is required for both Green and regression.
6. Set the task to `implemented`; retain the task file and its history inside the Change.

If implementation requires a new requirement, Decision, target change, undeclared path, or material scope expansion, stop and return the Change upstream. Never edit a test merely to obtain Green.

For `route: docs` or `ops`, write only the task `allowed_paths` (spec/changelog or ops/deploy files). Do not patch product `src/**`. Do not weaken Implement for `route: code`.
