# Integrating DeltaFuse

[**English**](using.md) | [Русский](using.ru.md)

DeltaFuse is installed as a versioned external framework. The product repository stores product state and a thin integration layer, but never a copy of canonical process documentation.

## Install

From a trusted DeltaFuse checkout or package:

```powershell
./scripts/init.ps1 -TargetDir C:\path\to\product
```

```bash
bash ./scripts/init.sh /path/to/product
```

The installer creates the following product structure without overwriting existing files by default:

```text
.deltafuse/config.yaml
.deltafuse/lock.yaml
AGENTS.md
docs/intake/
docs/changes/
docs/spec/
docs/decisions/
docs/archive/intake/
docs/archive/changes/
```

It also generates tool-specific skill snapshots in `.agents/skills/`, `.cursor/skills/`, and `.gemini/skills/`. Each snapshot is marked `DO NOT EDIT` and records the installed framework version, source URI, and content hash.

The installer does not create `docs/process/`, `docs/init/`, or `docs/todo/` in the product repository.

## Pinning and upgrades

`.deltafuse/config.yaml` specifies the requested framework version and repository settings, including `workflow.call_width` (`narrow` | `medium` | `wide`, default `wide`). `.deltafuse/lock.yaml` pins the resolved version, schema version, framework content hash, and the Analyze call-width profile. Re-run the installer after changing `call_width` so lock matches config.

Re-running the installer with `-Force` (PowerShell) or `--force` (Bash) performs an explicit framework upgrade. It updates the requested version in config, lock, and generated adapters, while preserving product-owned specification, Changes, Decisions, `AGENTS.md`, and any existing templates. Before updating lock:

1. Review active Changes and their recorded framework/schema versions.
2. Complete them on the current version or explicitly close the Change.
3. Regenerate adapters and validate product layout.

Never manually edit generated skills or create a local process fork. Product-specific routing and repository conventions belong in `.deltafuse/config.yaml` and the product's concise `AGENTS.md`.

## First operation

| Product state | Operation |
|---|---|
| No accepted specification baseline | Set `project.baseline: draft`, run `/intake`, then perform Bootstrap via Analyze and Specify |
| Accepted specification exists | Set `project.baseline: accepted`, create Changes via `/intake` |

The initial capability catalog is proposed by AI and accepted by a human. After acceptance, capability changes require explicit catalog deltas.

## Kernel evidence

Workers write tests and production files. The kernel records proof:

```text
deltafuse evidence <change-dir> --phase red --task TASK-001 --changed-path tests/test_foo.py -- pytest tests/test_foo.py -q
```

Import/syntax failures and `_`-prefixed Red tests are not authentic. `check-gate --gate targeting` still enforces the YAML on disk.

## External boards

A read-only UI (fuse-map) must consume the [board snapshot contract](./contracts/board-snapshot.md) for both cards and board layout (columns + steps). It must not parse `docs/changes/**` or hardcode the lifecycle. The installer does not copy `docs/contracts/**` into the product. Fuse-map pins `schema_version` in its own repository.
