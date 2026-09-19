# Artifact Writer Contract v1

**Contract Version:** 1  
**Target Storage Schemas:** v3  
**Framework Version:** 3.1.0  
**Schema URI:** `https://deltafuse.dev/contracts/artifact-writer/v1`  
**Receipt Schema URI:** `https://deltafuse.dev/contracts/artifact-writer/receipt/v1`  

## 1. Overview

The Artifact Writer contract defines the typed operation transport envelope, operation descriptors, receipt structure, patch protocol, and error diagnostics for the DeltaFuse Core serialization service.

It acts as a serialization and persistence protocol between callers (Workers, host wrappers, CLI) and DeltaFuse Core storage. It does **not** grant authorization to mutate Core-owned fields or execute lifecycle transitions.

---

## 2. Operation Envelopes

All operation requests pass a closed JSON/YAML request envelope validating against `docs/contracts/artifact-writer.schema.yaml`:

```yaml
request_id: "req-001"
operation: "create" # create | update | validate | describe
kind: "task"        # task | slice | spec-delta | routing | change | ...
change: "CHG-001"
identity: "TASK-001"
semantic_payload:
  title: "Add authentication handler"
  kind: "feature"
  allowed_paths: ["src/auth.py"]
```

### Fields:
- `request_id`: Required string identifier for transaction tracking and idempotency.
- `operation`: Required enum (`create`, `update`, `validate`, `describe`, `update-index`).
- `kind`: Required enum corresponding to one of the 10 storage schemas.
- `change`: Owning Change ID or relative directory path.
- `identity`: Specific artifact identifier (e.g. `TASK-001`) for `create` / `describe`.
- `target`: Relative file path (e.g. `tasks/TASK-001.md`) for `update` / `validate`.
- `expected_sha256`: Optional SHA256 digest of target file before update (concurrency control).
- `semantic_payload`: Object containing initial semantic fields on `create`.
- `patch`: Object containing JSON Pointer edits on `update`.
- `body`: Optional opaque markdown body content.
- `update-index`: Atomic update operation synchronizing `change.yaml` child lists from disk.

---

## 3. Patch Semantics

Updates use an explicit JSON Pointer patch language (`patch` property):

```yaml
patch:
  set:
    - path: "/title"
      value: "Updated Auth Title"
  remove:
    - "/design_ref"
  canonicalize_metadata: false
```

### Rules:
- `set`: List of `{path, value}` objects. `path` MUST be a valid JSON Pointer starting with `/`.
- `remove`: List of JSON Pointer strings starting with `/`. Cannot remove schema-required fields.
- `canonicalize_metadata`: Boolean opt-in authorizing frontmatter re-ordering/re-formatting if raw frontmatter differs from canonical codec output.
- Pointer targets MUST match updatable semantic fields defined in the target kind's descriptor. Core-owned fields (e.g. `/status`) are rejected.

---

## 4. Per-Kind Operation Descriptors

Operation descriptors reside in `process/artifact-operations/*.descriptor.yaml` and are indexed by `process/artifact-operations/manifest.json`.

| Kind | Allowed Operations | Public Semantic Fields | Core-Owned Fields |
|---|---|---|---|
| `task` | `create`, `update`, `validate`, `describe` | `title`, `kind`, `depends_on`, `requirement_delta`, `spec_refs`, `design_ref`, `allowed_paths`, `forbidden_paths`, `context_budget` | `id`, `change`, `slice`, `status` |
| `slice` | `create`, `update`, `validate`, `describe` | `title`, `primary_capability`, `related_capabilities`, `policies`, `spec_refs`, `claims`, `depends_on`, `context_budget` | `id`, `change`, `status` |
| `spec-delta` | `create`, `update`, `validate`, `describe` | `slices`, `added`, `modified`, `removed` | `change`, `status` |
| `routing` | `create`, `update`, `validate`, `describe` | `claims` | `change` |
| `change` | `update`, `validate`, `describe` | `title`, `intent`, `risk`, `source/request`, `source/intake_refs`, `analysis/summary` | `schema_version`, `id`, `status`, `framework`, `analysis/routing`, `deltas`, `slices`, `decisions`, `tasks`, `verification` |
| `decision` | `validate`, `describe` | `title`, `kind`, `owner`, `date`, `affects`, `supersedes`, `superseded_by` | `id`, `change`, `status` |
| `evidence` | `validate`, `describe` | None | All fields (kernel stamped) |
| `coverage` | `validate`, `describe` | None | `change`, `claims` |
| `capability` | `validate`, `describe` | None | `schema_version`, `domains`, `policies` |
| `lock` | `validate`, `describe` | None | `schema_version`, `framework` |

---

## 5. Durable Receipts

Every mutating operation returns a receipt conforming to `process/artifact-operations/receipt.schema.yaml`:

- `request_id`, `transaction_id`, `timestamp`
- `operation`, `kind`, `target`
- `operation_schema` (version and hash)
- `storage_schema` (kind, version=3, id, hash)
- `serializer_revision` (integer)
- `request_sha256`, `payload_sha256`, `previous_sha256`, `result_sha256`
- `changed` (boolean flag)
- `outcome` (`prepared`, `published`, `committed`, `recovered`, `failed`)
- `authority` (`actor`, `work_item`, `product_root`)
- `validation_scopes` (schema, policy, reference validation statuses)
- `receipt_sha256` (digest of receipt excluding self)

---

## 6. Exit Codes and Diagnostic Errors

Proposed CLI exit codes:
- `0`: Success / valid read-only validation.
- `2`: Invalid input, envelope, or schema validation failure.
- `3`: Authorization or Core-owned field write denied.
- `4`: Target SHA256 mismatch or concurrency lock failure.
- `5`: Persistence error or indeterminate transaction state.

An unavailable or corrupt installed Writer contract returns exit `5` with
`asset_resolution_failed` (stage `schema`, path `/`, message at most 512
characters). It performs no mutation and never falls back to a contract in the
caller's working directory. Reinstall a verified bundle, or regenerate the
bundle with `scripts/sync_assets.py` when developing from source.
