---
name: intake
description: Normalize a raw feature, bug, document, log, or review note into an immutable DeltaFuse Change request without consulting product specification or code. Use only for the first lifecycle step.
---

# Intake

Create the provenance root for one logical Change.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Worker (LLM)

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, and `check-gate`.

1. If the caller asked to continue existing work without an id, run `deltafuse next` and follow that step instead of creating another Change. Use this skill only to start a new Change.
2. Write only this step's artifacts (see Procedure).
3. Close with `deltafuse check-gate <change-dir> --gate intake`. Halt if it exits non-zero.
4. Then run `deltafuse next`. Do not choose the next slash command yourself.
5. Do not auto-accept Decisions or merge.

## Context

Read only:

- the user's current raw request and explicitly named files under configured `paths.intake`;
- `.deltafuse/config.yaml` and `.deltafuse/lock.yaml` for paths and pinned versions;
- the Change/request schemas or templates bundled with this skill installation.

Do not read `docs/spec/**`, Decisions, other Changes/tasks, tests, or product code.

## Procedure

1. Allocate a stable `CHG-NNN-<slug>` identifier without reusing archived IDs.
2. Create `docs/changes/<change-id>/change.yaml` with `status: normalized`, framework/schema version, source references, and no guessed classification.
3. Create `request.md` containing a concise summary and stable claim IDs (`CR-*` preferred).
4. Label each claim as observation, expectation, constraint, or hypothesis. Preserve unknowns explicitly. If a label was used as the ID (`O1`, `E1`), keep that ID; do not rewrite `request.md` after Intake.
5. Do not invent acceptance criteria, technical design, capability routing, or spec references.
6. If the source is a repository file, preserve its path/hash in provenance and move it to `docs/archive/intake/` only after the immutable request is complete.

Later clarification is appended as a revision or superseding claim. Never silently rewrite an earlier claim.

## Gate

Every material input statement is represented by a claim or explicitly excluded. Product artifacts remain unread and unchanged.
