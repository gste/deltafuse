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
5. Record sanitized commands, exit status, results, changed paths, and `spec unchanged` under `evidence/green/`.
6. Set the task to `implemented`; retain the task file and its history inside the Change.

If implementation requires a new requirement, Decision, target change, undeclared path, or material scope expansion, stop and return the Change upstream. Never edit a test merely to obtain Green.

Recommend the next ready `/target-task`, or `/verify-change <change-id>` when all tasks are terminal.
