---
name: intake
description: Normalize a raw feature, bug, document, log, or review note into an immutable DeltaFuse Change request without consulting product specification or code. Use only for the first lifecycle step.
---

# Intake

Create the provenance root for one logical Change.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Context

Read only:

- the user's current raw request and explicitly named files under configured `paths.intake`;
- `.deltafuse/config.yaml` and `.deltafuse/lock.yaml` for paths and pinned versions;
- the Change/request schemas or templates bundled with this skill installation.

Do not read `docs/spec/**`, Decisions, other Changes/tasks, tests, or product code.

## Procedure

1. Allocate a stable `CHG-NNN-<slug>` identifier without reusing archived IDs.
2. Create `docs/changes/<change-id>/change.yaml` with `status: normalized`, framework/schema version, source references, and no guessed classification.
3. Create `request.md` containing a concise summary and stable `CR-*` claims.
4. Label each claim as observation, expectation, constraint, or hypothesis. Preserve unknowns explicitly.
5. Do not invent acceptance criteria, technical design, capability routing, or spec references.
6. If the source is a repository file, preserve its path/hash in provenance and move it to `docs/archive/intake/` only after the immutable request is complete.

Later clarification is appended as a revision or superseding claim. Never silently rewrite an earlier claim.

## Gate

Every material input statement is represented by a claim or explicitly excluded. Product artifacts remain unread and unchanged.

Return the Change path and recommend `/analyze-change <change-id>`.
