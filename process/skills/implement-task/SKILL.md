---
name: implement-task
description: Implement one DeltaFuse task against accepted specification and a frozen failing target, then record Green evidence. Use only after target-task has confirmed Red.
---

# Implement Task

Make one frozen target Green with the smallest compliant production change.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Context

Read one task, exact spec references, frozen target test, Red evidence, allowed production files/symbols, and only required local dependencies.

Do not change specification, Decisions, task scope, target oracle/assertions, or unrelated code.

## Procedure

1. Verify the task is `target-confirmed` and Red evidence matches the frozen target.
2. Implement the minimum production change inside allowed scope.
3. Run the targeted test until Green.
4. Run the declared scoped regression suite for unchanged behavior.
5. Record sanitized commands, exit status, results, changed paths, `spec unchanged`, and `base_revision` (content hash of current `docs/spec/**` and `src/**`) under `evidence/green/<task-id>.yaml` and `evidence/regression/<task-id>.yaml`. `changed_paths` must stay inside `PHASE_CONTRACTS` Implement write scope and outside the task `forbidden_paths`.
6. Set the task to `implemented`; retain the task file and its history inside the Change.

If implementation requires a new requirement, Decision, target change, undeclared path, or material scope expansion, stop and return the Change upstream. Never edit a test merely to obtain Green.

Recommend the next ready `/target-task`, or `/verify-change <change-id>` when all tasks are terminal.

For `route: docs` or `ops`, write only the task `allowed_paths` (spec/changelog or ops/deploy files). Do not patch product `src/**`. Do not weaken Implement for `route: code`.
