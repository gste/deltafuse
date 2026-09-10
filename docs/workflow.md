# Workflow

[**English**](workflow.md) | [Русский](workflow.ru.md)

DeltaFuse establishes a specification-driven, context-sliced development lifecycle. Every modification is processed through strictly bounded steps, deterministic evidence, and cross-artifact convergence.

```text
Request -> Analyze -> Delta -> Fuse -> Converge
```

---

## Lifecycle Overview

```text
Intake
  -> Analyze
  -> Specify
  -> Decompose
  -> Declare
  -> Implement
  -> Verify
```

---

## 1. Intake

### Purpose
Normalize an incoming raw request (issue, chat transcript, bug report, review note) into an immutable, structured Change package without consulting product specification or source code.

### Context Contract
- **Allowed Read Scope**: Raw user prompt, issue text, logs, bug attachments.
- **Forbidden Read Scope**: `docs/spec/**`, repository source code, existing tasks.

### Rules
1. Allocate a unique Change ID matching `CHG-[0-9]{3,}(-[a-z0-9-]+)?` (e.g., `CHG-001-user-auth`).
2. Create `docs/changes/<change-id>/request.md` with:
   - Verbatim user request preserved intact;
   - Normalized context;
   - Extracted atomic claims numbered sequentially (`CR-001`, `CR-002`, etc.);
   - Non-functional requirements, constraints, and known uncertainties.
3. Initialize `docs/changes/<change-id>/change.yaml` with `status: normalized`.
4. The Intake step must never guess implementation details or propose architecture.

### Gate
- `change.yaml` passes `change.schema.yaml` with `status: normalized`.
- `request.md` contains at least one atomic claim (`CR-001`).
- Neither `docs/spec/**` nor product source code was read during this step.

---

## 2. Analyze

### Purpose
Route normalized claims to capabilities from `docs/spec/_capabilities.yaml`, compute typed deltas, detect contradictions, and formulate architectural decisions.

### Pass A: Routing
1. Read `request.md`, `docs/spec/_capabilities.yaml`, and compact global policy summaries.
2. Map each claim (`CR-*`) to its owning primary capability:
   - **Matched**: claim maps cleanly to an existing capability;
   - **Ambiguous**: claim spans or conflicts across multiple capabilities;
   - **Capability-Gap**: claim requires behavior not covered by any existing capability.
3. Record mapping and confidence scores in `routing.yaml`.

Routing is always the first Analyze write. `.deltafuse/config.yaml` `workflow.call_width` (`narrow` | `medium` | `wide`, default `wide`) is pinned in `.deltafuse/lock.yaml`. `narrow` writes routing, then slices, then coverage across invocations; `medium` writes routing, then slices and coverage together; `wide` may finish Analyze in one invocation. Status stays `analyzing` until all three artifacts exist. Call width does not skip Specify and does not auto-accept Decisions.

### Pass B: Slice Analysis
For each capability slice:
1. Load only the specification modules referenced by the capability.
2. Formulate `slices/SLICE-NN.md` defining scope, primary capability, and dependencies. Write one slice file per primary capability; a two-capability Change produces `SLICE-01` and `SLICE-02`. Do not emit only `SLICE-01`.
3. Compute an explicit typed delta (`DELTA-NN`) across the 7 normative projections defined in `change.schema.yaml`:
   - `specification`: `none | add | modify | remove | mixed` (with `refs` to affected spec files/sections);
   - `catalog`: `none | add | modify | remove` (with `refs` to capability IDs in `_capabilities.yaml`);
   - `decisions`: `none | propose | supersede` (with `refs` to proposed/superseded `DEC-*` records);
   - `tasks`: `none | derive | modify | remove` (with `refs` to derived tasks);
   - `tests`: `none | add | modify | remove` (with `refs` to test files);
   - `implementation`: `none | add | modify | remove | mixed` (with `refs` to production code roots);
   - `evidence`: `none | record` (with `refs` to evidence files).
   Assign delta `kind`: `requirements | conformance | structural | operational | mixed`.
4. Optionally record analysis narrative in `analysis.md`. The `analyzed` gate does not require it.
5. Map claims to slices, tasks, spec references, and evidence in `coverage.yaml`.

### Typed Delta Invariants
- If `specification.operation` is `none`, the Change does not alter accepted specification; it is classified as an **Implementation Bug** or **Refactoring**, and the **Specify** step records formal proof in `spec-delta.md` that existing specification already requires the behavior.
- If `specification.operation` is `add`, `modify`, `remove`, or `mixed`, the Change MUST pass through the **Specify** step to update `docs/spec/**`.
- If `catalog.operation` is `add`, `modify`, or `remove`, a catalog delta for `_capabilities.yaml` is required (Human Gate: Capability Boundary).
- If `decisions.operation` is `propose`, new decision records are drafted in `docs/decisions/DEC-*` with `status: proposed`, and the Change transitions to `blocked-on-decision` until human approval.

### Analytical Outcomes
- **Feasible**: all claims mapped, deltas computed, ready for specification or targeting.
- **Decision Required**: architectural or product uncertainty identified; create `docs/decisions/DEC-NNNN-*.md` in `status: proposed` and transition Change to `blocked-on-decision`.
- **Capability Gap**: new capability required; draft catalog delta for `_capabilities.yaml` requiring human approval.
- **Duplicate**: Change duplicates an existing active or archived Change; mark `duplicate`.
- **Rejected**: Request conflicts with core architecture or is unfeasible; mark `rejected`.

### Decision Convergence Loop
If decisions are required:
```text
Analyze -> Draft DEC-NNNN (proposed) -> Human Gate -> Decision (accepted/rejected) -> Re-analyze
```
Analysis repeats iteratively until zero blocking decisions remain in `proposed`.

### Gate
- `change.yaml` status transitioned to `analyzed` (or `blocked-on-decision`).
- `routing.yaml` validates against `routing.schema.yaml`.
- `coverage.yaml` validates against `coverage.schema.yaml`.
- Each slice validates against `slice.schema.yaml`.
- Zero unresolved blocking decisions.
- The `analyzed` gate does not close until routing, slices, and coverage are on disk, regardless of `workflow.call_width`.
- Set `route` on `change.yaml` and `routing.yaml` to `code` (default), `docs`, or `ops`. Missing `route` is `code` (S02/S03). `docs`/`ops` still pass Specify; they do not take product pytest or `src/**` writes.
- Unknown top-level keys on `routing.yaml` (including `schema_version`) do not fail `analyzed`. Two slice files do not satisfy Specify without live `docs/spec/**`.
- `analysis.md` is optional. `analyzed` requires routing, slices, and coverage, not a summary file.

---

## 3. Specify

### Purpose
Apply analyzed specification deltas to the authoritative product specification in `docs/spec/**`, or verify that the accepted specification is unchanged.

### Context Contract
- **Allowed Read Scope**: `request.md`, slices, target spec modules, accepted decisions, and `analysis.md` when present.
- **Forbidden Read Scope**: Product implementation source code.

### Rules
1. Draft the specification diff in `docs/changes/<change-id>/spec-delta.md`.
2. Update normative requirement files under `docs/spec/**` in imperative, unambiguous language. Use RFC 2119 `MUST` / `MUST NOT` / `SHOULD` / `MAY` (or `ДОЛЖЕН` / `НЕ ДОЛЖЕН`). Prefer EARS: WHEN [condition] THE SYSTEM SHALL [observable behavior]. EARS is style, not a new file format and not a Specify gate.
3. Every new or modified requirement must be traceable to at least one `CR-*` claim.
4. If specification delta was marked with operation `none` during analysis (Implementation Bug), record explicit proof in `spec-delta.md` that existing specification already mandates the requested behavior.

### Gate
- `spec-delta.md` validates against `spec-delta.schema.yaml` (`added`, `modified`, and `removed` required).
- Added or modified paths exist under `docs/spec/**` with their anchors.
- `docs/spec/_capabilities.yaml` validates against the capability schema and lists each slice `primary_capability` with live spec files.
- If `added` and `modified` are empty (`requirement_delta: none`), each slice `spec_refs` cites an existing `#REQ-*` / `#SC-*` anchor.
- Specification changes reviewed and approved by human maintainer (Human Gate: Spec).
- `change.yaml` status is `specified` or `specification-proposed`.
- Product source code is not required at this gate.
- EARS phrasing does not replace live `docs/spec/**` (F-010).

---

## 4. Decompose

### Purpose
Decompose each specified slice into atomic, dependency-ordered task files inside `docs/changes/<change-id>/tasks/`.

### Context Contract
- **Allowed Read Scope**: Updated `docs/spec/**`, slice definitions, target test suite signatures.
- **Forbidden Read Scope**: Full codebase exploration.

### Atomic Task Contract
Each task is authored in `tasks/TASK-NNN-<slug>.md` with YAML frontmatter conforming to `task.schema.yaml`:
```yaml
---
id: TASK-001
change: CHG-001-user-auth
slice: SLICE-01
kind: feature
status: pending
depends_on: []
requirement_delta: added
spec_refs:
  - docs/spec/identity/authentication.md#REQ-AUTH-001
design_ref: null
allowed_paths:
  - src/identity/auth/**
  - tests/identity/auth/**
forbidden_paths:
  - src/identity/session/**
context_budget:
  max_tokens: 16000
  max_files: 24
---
```

The Markdown body defines the operational contract:
```markdown
# Task outcome

## Outcome
Validate credentials and issue an initial access token.

## Test oracle
- GIVEN valid user credentials
- WHEN authentication is requested
- THEN return HTTP 200 with access token
- GIVEN invalid password
- WHEN authentication is requested
- THEN fail with HTTP 401 Unauthorized

## Unchanged behavior
- Existing session revocation and refresh endpoints remain unaffected.

## Verification
- Targeted command: `pytest tests/identity/auth/test_auth.py`
- Regression command: `pytest tests/identity/`
```

### Gate
- All tasks validate against `task.schema.yaml` and declare `context_budget`.
- Declared `allowed_paths` and evidence `changed_paths` stay inside `PHASE_CONTRACTS` write globs for Declare/Implement.
- Task dependencies form an acyclic directed graph (DAG).
- All claims in `coverage.yaml` mapped to at least one task.
- `change.yaml` status transitioned to `decomposed`.

---

## 5. Declare

### Purpose
Declare what must become true for one atomic task: freeze a Red oracle that fails on unchanged production code for the expected reason. Writing that Red test before Implement is the declaration.

### Context Contract
- **Allowed Read Scope**: Single `TASK-NNN.md`, target test file, public API signatures of target module.
- **Forbidden Read Scope**: Production implementation code under test.

### Rules
1. Implement the minimal test case in the file indicated by `test_target`.
2. Execute the test target against the unmodified codebase with the kernel:
   `deltafuse evidence <change-dir> --phase red --task <task-id> --changed-path <test-rel> -- <command>`.
   Do not hand-write `evidence/red/*.yaml`.
3. Verify that the test fails exclusively due to the missing feature or bug, not due to syntax errors, import failures, or broken fixtures. Authentic Red is CLI exit 0 (`failure_category: behavioral-mismatch`).
4. The runner records execution proof in `evidence/red/<task-id>.yaml` conforming to `evidence.schema.yaml`:
   ```yaml
   schema_version: 2
   change: CHG-001-user-auth
   task: TASK-001
   phase: red
   timestamp: "2026-09-04T12:00:00Z"
   command: pytest tests/identity/auth/test_auth.py::test_expired_token
   exit_code: 1
   result: expected-failure
   failure_category: behavioral-mismatch
   summary: "AssertionError: Expected 401 Unauthorized, got 200 OK"
   changed_paths: []
   spec_status: unchanged
   ```
5. Transition task status to `target-confirmed`.
6. Optional: add Hypothesis-class property tests as extra oracles. Skip if no local runner. PBT does not replace the GWT example Red test or the independent hidden suite. Do not add `.kiro` or Cucumber.

### Gate
- Executable test fails with the expected failure signature, **or** the public oracle already passes and evidence result is `already-green`.
- Red tests listed in `changed_paths` must not access `_`-prefixed product internals.
- `evidence/red/<task-id>.yaml` exists and validates against `evidence.schema.yaml`.
- Task status transitioned to `target-confirmed`.
- Hidden / independent suites are not replaced by the agent's tests.
- Property-based tests are optional Declare extras; missing a local runner is skip, not a gate fail.

---

## 6. Implement

### Purpose
Author the minimal production code necessary to turn the failing test target green without introducing regressions.

### Context Contract
- **Allowed Read Scope**: Single `TASK-NNN.md`, Red evidence, target test, target implementation source file.
- **Forbidden Read Scope**: Unrelated modules and packages.

### Rules
1. Author only the production code required to satisfy the test assertions.
2. Execute the test target and prove it passes via the kernel:
   `deltafuse evidence <change-dir> --phase green --task <task-id> --changed-path <rel> -- <command>`.
   Do not hand-write evidence YAML.
3. Execute the capability/domain regression test suite the same way (`--phase regression`).
4. Transition task status to `implemented`.

### Gate
- Test target passes cleanly.
- Full regression suite passes without failures.
- `evidence/green/<task-id>.yaml` and `evidence/regression/<task-id>.yaml` recorded and valid, each with `base_revision` matching the current `docs/spec/**` and `src/**` content hash.
- Task status transitioned to `implemented`.

---

## 7. Verify

### Purpose
Verify cross-artifact consistency across all layers of the Change package, verify that all tasks are green, confirm claim coverage, and archive the completed package.

### Traceability Verification
The Verifier checks that:
1. Every normalized claim in `request.md` (`CR-*` or stable labels such as `O1`/`E1`) traces to a slice in `routing.yaml`.
2. Every claim traces to an accepted requirement in `docs/spec/**` (or proven `unchanged` for bugfixes).
3. Every claim traces to at least one completed task in `coverage.yaml`.
4. Every task has verified `red`, `green`, and `regression` evidence artifacts.
5. Active tasks in the Change are transitioned to `verified`. `cancelled` and `superseded` tasks remain in those terminal statuses.

### Convergence Analysis
1. Execute full project verification suite.
2. Record change-level verification evidence in `evidence/verification/run.yaml` (`phase: verification`, `task: null`, `base_revision` matching current `docs/spec/**` and `src/**`).
3. Generate `docs/changes/<change-id>/verification.md` detailing:
   - Traceability matrix;
   - Evidence audit;
   - Delta verification;
   - Residual risks and verification sign-off.
4. Transition `change.yaml` status to `converged`. The gate fails if `spec-delta.md` `added`/`modified` files or anchors are missing from `docs/spec/**`, or if `removed` entries are still present. Archive does not merge specification.

### Archiving
After `deltafuse check-gate <change-dir> --gate converged` passes, run `deltafuse archive <change-dir>`. That:
1. Moves the complete Change directory from `docs/changes/<change-id>` to `docs/archive/changes/<date>-<change-id>`.
2. Updates any related intake requests in `docs/intake/` and moves them to `docs/archive/intake/`.
3. Updates `change.yaml` status to `archived`.
4. Leaves the archived Change package as an immutable historical record.

---

## Defect Classification (Bug Workflow)

### 1. Implementation Bug
- **Definition**: Production code deviates from existing accepted specification.
- **Workflow**:
  1. Intake normalizes report into `CHG-NNN`.
  2. Analyze verifies that existing specification already requires the expected behavior (`specification.operation: none`).
  3. Specify transitions Change from `analyzed` to `specified`, recording proof in `spec-delta.md` that existing specification already requires the behavior without modifying normative spec.
  4. Decompose creates bugfix task.
  5. Declare writes the Red oracle (what must become true); records Red evidence.
  6. Implement fixes code; records Green & Regression evidence.
  7. Verify checks convergence and archives package.

### 2. Specification Bug
- **Definition**: Existing specification is incomplete, ambiguous, or incorrect.
- **Workflow**: Standard 7-step Change with `spec-delta.md` modifying `docs/spec/**` through Human Gate.

### 3. Not a Bug
- **Definition**: Reported behavior matches accepted specification and product intent.
- **Workflow**: Intake -> Analyze (Decision: Rejected / Closed) -> Verify / Archive with explanatory evidence.

---

## Bootstrap Profile

When initializing a new product repository:
1. `.deltafuse/config.yaml` starts with `project.baseline: draft`.
2. Initial capability catalog `docs/spec/_capabilities.yaml` is drafted.
3. Foundational architecture decisions and global policies are resolved in `docs/decisions/**` (with `change: null`).
4. Core baseline specification is authored in `docs/spec/**`.
5. Once baseline is approved by human maintainer, `project.baseline` transitions to `accepted`.
6. Subsequent modifications must proceed exclusively through DeltaFuse Changes.

---

## Completion Criteria

A DeltaFuse Change is considered complete when:
- All claims (`CR-*`) are traced to passing tests and accepted specification.
- All tasks are in `verified` status.
- Red, Green, Regression, and Verification evidence files are recorded and valid.
- Package is archived in `docs/archive/changes/<date>-<change-id>/`.
