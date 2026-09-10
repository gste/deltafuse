---
name: declare
description: Declare what must become true for one DeltaFuse task by writing a Red oracle that fails on unchanged production code. Use before /implement.
---

# Declare

Declare the behavior that must become true. That is the point of writing Red tests before Implement.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Context

Read one task, exact spec references, reproduction and unchanged behavior, relevant test conventions/fixtures/helpers, and only public product interfaces needed to express the oracle.

Do not read implementation internals unless the oracle cannot otherwise be expressed. Do not change production code, specification, Decisions, or the task's expected behavior.

## Procedure

1. Confirm task dependencies and normative references are ready.
2. Freeze the declared oracle from the task and specification: what must become true.
3. Add or modify the smallest automated test that demonstrates the missing behavior or defect.
4. Run that test against unchanged production code.
5. Require a failure caused by the expected behavior, not compilation, fixture, environment, or unrelated failures.
6. Record sanitized command, exit status, failure category, and concise result under the Change's `evidence/red/`. `changed_paths` must stay inside `PHASE_CONTRACTS` Declare write scope (`tests/**`, Red evidence); do not list production `src/**`.
7. Set task/Change state to `target-confirmed` only after valid Red.

If already Green, invalid, environment-blocked, or not reproduced, stop and return that outcome upstream. Record `already-green` when the public oracle already passes. Do not access `_`-prefixed product internals to manufacture Red. Do not weaken assertions to manufacture Red.

Recommend `/implement <task-path>` only for confirmed Red.

For `route: docs` or `ops`, record a file or schema oracle in `evidence/red/` instead of product pytest; do not list `src/**` or `tests/**`. Hidden code-suite checks do not apply.

Optional: add Hypothesis-class property tests as extra oracles for an invariant. Skip if no local runner. PBT does not replace the GWT example Red test or the independent hidden suite. Do not add `.kiro` or Cucumber as Declare.
