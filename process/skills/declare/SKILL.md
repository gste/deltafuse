---
name: declare
description: Declare what must become true for one DeltaFuse task by writing a Red oracle that fails on unchanged production code. Use before /implement.
---

# Declare

Declare the behavior that must become true. That is the point of writing Red tests before Implement.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

If the caller did not name a Change or task, run `deltafuse next --step declare` at the product root and use `path` / `task_path`. If it exits non-zero, stop and report the output.

## Context

Read one task, exact spec references, reproduction and unchanged behavior, relevant test conventions/fixtures/helpers, and only public product interfaces needed to express the oracle.

Do not read implementation internals unless the oracle cannot otherwise be expressed. Do not change production code, specification, Decisions, or the task's expected behavior.

## Procedure

1. Confirm task dependencies and normative references are ready.
2. Freeze the declared oracle from the task and specification: what must become true.
3. Add or modify the smallest automated test that demonstrates the missing behavior or defect.
4. Run that test against unchanged production code by calling the kernel, not by hand-writing YAML:
   `deltafuse evidence <change-dir> --phase red --task <task-id> --changed-path <test-rel> -- <command>`.
5. Require CLI exit 0 (authentic Red): expected behavior failure (`behavioral-mismatch`), not compilation, import, fixture, environment, or `_`-prefixed internals. Import/syntax still write YAML but are not a gate pass.
6. `changed_paths` must stay inside `PHASE_CONTRACTS` Declare write scope (`tests/**`, Red evidence); do not list production `src/**`.
7. Set task/Change state to `target-confirmed` only after valid Red.

If already Green, invalid, environment-blocked, or not reproduced, stop and return that outcome upstream. Record `already-green` when the public oracle already passes. Do not access `_`-prefixed product internals to manufacture Red. Do not weaken assertions to manufacture Red.

Recommend `/implement <task-path>` only for confirmed Red.

For `route: docs` or `ops`, record a file or schema oracle in `evidence/red/` instead of product pytest; do not list `src/**` or `tests/**`. Hidden code-suite checks do not apply.

Optional: add Hypothesis-class property tests as extra oracles for an invariant. Skip if no local runner. PBT does not replace the GWT example Red test or the independent hidden suite. Do not add `.kiro` or Cucumber as Declare.
