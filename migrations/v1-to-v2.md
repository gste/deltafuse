# DeltaFuse v1 to v2 Migration

DeltaFuse v2 is a breaking process migration. Perform it as a reviewed repository change; do not mix it with product implementation.

## Semantic changes

| v1 | v2 |
|---|---|
| `docs/inbox/` | `docs/intake/` |
| `docs/todo/<story>/**` | `docs/changes/<change-id>/tasks/**` |
| `docs/init/` and `docs/process/STATUS.md` | `.deltafuse/config.yaml` `project.baseline` |
| Product-local `docs/process/**` | Pinned external DeltaFuse framework |
| Binary ADR `accepted: false/true` | General Decision with `kind` and lifecycle `status` |
| `/triage` | `/intake`, then `/analyze-change` |
| `/audit-spec` | Decision convergence in `/analyze-change`, then `/specify-change` |
| `/plan-story` | `/decompose-change` |
| `/implement-task` performing Red+Green | `/target-task`, then `/implement-task` |
| Deleted completed task | Task history retained and archived with its Change |

## Preparation

1. Start from a clean worktree or record all pre-existing changes.
2. Create a migration branch and a recoverable backup/tag under human control.
3. Inventory active `docs/todo/**`, open Decisions, copied process files, and generated tool skills.
4. Stop product implementation until the migration validates.

## Artifact migration

1. Install DeltaFuse v2 to create `.deltafuse/config.yaml`, `.deltafuse/lock.yaml`, product directories, and generated adapters.
2. Move raw unprocessed `docs/inbox/**` into `docs/intake/**`; move processed `docs/archive/inbox/**` into `docs/archive/intake/**`.
3. Set `project.baseline: accepted` only if the current specification was already human-accepted. Otherwise keep `draft` and use Bootstrap.
4. For each active v1 story, create an owning Change package with `change.yaml`, immutable `request.md`, routing/analysis, slices, and coverage.
5. Move each legacy task into that Change's `tasks/` and convert it to the v2 task schema. Do not guess ownership when one story spans unrelated outcomes; split it into multiple Changes and preserve provenance.
6. Convert each Decision:
   - allocate `DEC-NNNN` identity;
   - choose `kind: product | architecture | integration | policy | operational`;
   - map `accepted: false` to `status: proposed`;
   - map `accepted: true` to `status: accepted` only when human acceptance is evidenced;
   - add owner, owning Change, affected capabilities, and spec references.
7. Move bootstrap inputs from `docs/init/**` to `docs/intake/**` if still active or `docs/archive/intake/**` if already processed.
8. Remove the product-local `docs/process/**` only after the external v2 pin and generated skills are available. Preserve the old copy in migration history rather than an active runtime path.
9. Remove empty legacy `docs/init/**` and `docs/todo/**` paths.

## Active Change versioning

Every migrated `change.yaml` must record:

```yaml
schema_version: 2
framework:
  version: 2.0.0
  content_hash: <value from .deltafuse/lock.yaml>
```

Do not change this metadata mid-Change without migrating the entire package and re-running analysis/convergence checks.

## Validation

Run the platform validator from the pinned DeltaFuse package:

```powershell
./validators/validate-layout.ps1 -ProductDir C:\path\to\product
```

```bash
bash ./validators/validate-layout.sh /path/to/product
```

Then confirm:

- all raw sources map to immutable `CR-*` claims;
- every claim has one owning capability;
- every active task belongs to one Change/slice and has exact spec references plus an oracle;
- accepted Decision effects are mirrored into specification where normative;
- no active product path uses `docs/process`, `docs/init`, or `docs/todo`;
- generated skill version/hash matches `.deltafuse/lock.yaml`.

Commit the migration separately from product behavior changes.
