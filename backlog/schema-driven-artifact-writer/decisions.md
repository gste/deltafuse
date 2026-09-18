# Schema-driven Artifact Writer — Design Decisions & Catalog Freeze (AW-00)

**Framework Version:** 3.1.0  
**Baseline HEAD Commit:** `17786cb040d1ed3cd5636dd4a6b97453c1b77627`  
**Date:** 2026-09-18  

## 1. Inventory of Storage Schemas and Authority Catalog

The framework defines 10 canonical storage schemas under `process/schemas/`. The Artifact Writer exposes controlled operations over these kinds according to explicit ownership boundaries:

| Kind | Storage Schema | Public Operations (Worker) | Publicly Modifiable Semantic Fields | Core-Owned Fields & Constraints | Initial Status / Defaults |
|---|---|---|---|---|---|
| `task` | `process/schemas/task.schema.yaml` | `create`, `update`, `validate` | `title`, `kind`, `depends_on`, `requirement_delta`, `spec_refs`, `design_ref`, `allowed_paths`, `forbidden_paths`, `context_budget` | `id`, `change`, `slice`, `status` (Core transitions via `set_artifact_status`) | Default status on `create`: `"pending"`. Required fields must be provided; no semantic fallback. |
| `slice` | `process/schemas/slice.schema.yaml` | `create`, `update`, `validate` | `title`, `primary_capability`, `related_capabilities`, `policies`, `spec_refs`, `claims`, `depends_on`, `context_budget` | `id`, `change`, `status` (Core transitions via `set_artifact_status`) | Default status on `create`: `"draft"`. |
| `spec-delta` | `process/schemas/spec-delta.schema.yaml` | `create`, `update`, `validate` | `slices`, `added`, `modified`, `removed` | `change`, `status` (Core `decide` command controls state transitions) | Default status on `create`: `"proposed"`. |
| `routing` | `process/schemas/routing.schema.yaml` | `create`, `update`, `validate` | `claims` (`summary`, `primary_capability`, `related_capabilities`, `policies`, `confidence`) | `change` (bound to current Change directory identity) | Derived during Analyze pass. |
| `change` | `process/schemas/change.schema.yaml` | `update` (selected fields), `validate` | `title`, `intent`, `risk`, `source.request`, `source.intake_refs`, `analysis.summary` | `schema_version` (const 3), `id`, `framework`, `status`, `analysis.routing`, `deltas`, `slices`, `decisions`, `tasks`, `verification` | `create` executed via `deltafuse init` / `scaffold_change`. Core-managed mirrored child lists. |
| `evidence` | `process/schemas/evidence.schema.yaml` | `validate` only | None (Worker cannot call public writer to create or modify evidence) | All fields (`schema_version`, `change`, `task`, `phase`, `timestamp`, `command`, `exit_code`, `result`, `failure_category`, `summary`, `changed_paths`, `spec_status`, `base_revision`, `recorded_by`, `recorded_sha256`) owned by `deltafuse evidence` | Stamped exclusively by Core execution engine. |
| `coverage` | `process/schemas/coverage.schema.yaml` | `validate` only | None | All fields (`change`, `claims`) derived and serialized by Core `coverage` command | Derived directly from actual Change artifacts and evidence. |
| `decision` | `process/schemas/decision.schema.yaml` | `validate` (initially) | `title`, `kind`, `owner`, `date`, `affects`, `supersedes`, `superseded_by` | `id`, `change`, `status` (Core `decide` accepts/rejects decisions) | Status managed via Human Gate / Core. |
| `capability` | `process/schemas/capability.schema.yaml` | `validate` only | None (Worker edits catalog via existing spec files under Human Gate) | All catalog governance fields | Root spec asset. |
| `lock` | `process/schemas/lock.schema.yaml` | Read-only | None | All fields (`schema_version`, `framework.version`, `framework.content_hash`) | Managed exclusively by installer/upgrade tooling. |

## 2. Rejecting Invalid & Nonexistent Kinds / Properties

To prevent state forgery and semantic drift:
- **Unsupported Kinds:** Nonexistent kinds (e.g. `requirement_delta`, `request_prose`, `verification_narrative`) are rejected by the descriptor catalog registry with error code `unsupported_kind`.
- **Core-Owned Status Modifications:** Any patch attempting to write to `status`, `framework`, `recorded_sha256`, or `schema_version` via public Worker `create` or `update` operations is rejected with error code `core_owned_field`.
- **Universal `schema_version` Injection:** `schema_version` is required only on top-level standalone schemas (`change`, `evidence`, `capability`, `lock`). Injecting `schema_version: 3` into nested schemas (`task`, `slice`, `routing`, `spec-delta`, `decision`, `coverage`) is rejected when `additionalProperties: False`.

## 3. Explicit Two-Step Child and Parent Index Updates

Child creation (`task`, `slice`, `spec-delta`, `decision`) is strictly single-file atomic. The public Artifact Writer does NOT perform implicit multi-file mutations (such as automatically appending the new task ID to `change.yaml`'s `tasks` list during task creation).

Child indexing is an explicit second operation:
1. Step 1: Create child artifact (`tasks/TASK-001.md`).
2. Step 2: Call Core index update (`update_change_index` / `change.yaml` child synchronization) where Core resolves the child identity and current status from the actual child file on disk.

## 4. Format Assertions, Metadata Canonicalization, and Extension Policy

- **Format Assertions:** Strict YAML/JSON parser rules. Duplicate keys, custom tags, non-string keys, invalid scalar coercions (unquoted dates, `yes`/`no` booleans), and non-finite float values are rejected at the bounded reader stage before schema validation.
- **Metadata Canonicalization:** Frontmatter key order is standardized per descriptor. When existing frontmatter differs in formatting/ordering from canonical output, the writer requires explicit `canonicalize_metadata: true` with an expected `previous_sha256` hash to authorize re-formatting. Opaque markdown body bytes are preserved byte-for-byte.
- **Nested Extension Fields:** Unrecognized top-level extension fields are permitted only on schemas with `additionalProperties: True` (`coverage`, `routing`). For closed schemas (`additionalProperties: False`), unexpected fields fail validation. Public operation schemas define a closed subset of allowed input fields.

## 5. Version Impact Statement

- Artifact Storage Schema version: `v3` (unchanged).
- Artifact Writer Operation Schema version: `v1` (new transport and descriptor protocol).
- DeltaFuse Framework version: `3.1.0`.
- Serializer Revision: `1`.
