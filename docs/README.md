# DeltaFuse Process

[**English**](README.md) | [Русский](README.ru.md)

DeltaFuse is a context-sliced, specification-driven workflow that turns raw intent into verified code through small, strictly bounded contexts.

Two names stay distinct: **Process** (the lifecycle machine) and **Thinker** (LLM or human who writes Change files). See [process-and-thinker.md](./process-and-thinker.md).

```text
Request -> Analyze -> Delta -> Fuse -> Converge
```

- **Change** — full lifecycle container.
- **Delta** — typed difference set computed during analysis.
- **Fuse** — applying Delta only to affected artifact layers.
- **Convergence** — proof of consistency across claims, specification, tasks, tests, and code.

## Canonical boundary

This directory is canonical only inside the DeltaFuse framework repository. Consuming product repositories must not copy `docs/**`.

A product pins the framework through:

```text
.deltafuse/config.yaml
.deltafuse/lock.yaml
```

The installer can generate repository-local skills for specific AI tools. These are immutable snapshots with framework version, source, and content hash, not a second source of process truth. Product-specific behavior remains outside the framework.

## Sources of truth

| Question | Authoritative source in product repository |
|---|---|
| Required product behavior | `docs/spec/**` |
| Questions, trade-offs, and rationale | `docs/decisions/**` |
| What is changing now and why | `docs/changes/<change-id>/**` |
| Executable work items | `docs/changes/<change-id>/tasks/**` |
| Proven behavior evidence | Tests and evidence artifacts |
| Implementation details | Product code |
| Process mechanics | Pinned external framework |

Only `docs/spec/**` is implementation law. Raw intake, Change requests, Decisions, tasks, chat, diffs, and archive cannot override accepted specification.

## Lifecycle

```text
Intake
  -> Analyze
  -> Specify
  -> Decompose
  -> Declare
  -> Implement
  -> Verify
```

`Red` and `Green` are evidence states inside Declare and Implement, not top-level steps.

## Product artifact layout

```text
product/
├── AGENTS.md
├── .deltafuse/
│   ├── config.yaml
│   └── lock.yaml
└── docs/
    ├── intake/
    ├── changes/
    │   └── <change-id>/
    │       ├── change.yaml
    │       ├── request.md
    │       ├── routing.yaml
    │       ├── analysis.md          # optional
    │       ├── slices/
    │       ├── tasks/
    │       ├── evidence/
    │       └── verification.md
    ├── spec/
    ├── decisions/
    └── archive/
        ├── intake/
        └── changes/
```

There are no product-local `docs/process/`, `docs/init/`, or `docs/todo/`. Bootstrap is a profile controlled by `project.baseline`; tasks belong to their owning Change.

## Canonical documents

| Document | Purpose |
|---|---|
| [process-and-thinker.md](./process-and-thinker.md) ([ru](./process-and-thinker.ru.md)) | Process vs Thinker: kernel vs LLM/human who writes files |
| [workflow.md](./workflow.md) ([ru](./workflow.ru.md)) | Lifecycle, gates, bugs, Bootstrap, and convergence |
| [state-machine.md](./state-machine.md) ([ru](./state-machine.ru.md)) | Change, slice, task, and Decision states |
| [context-model.md](./context-model.md) ([ru](./context-model.ru.md)) | Domain routing, slicing, and context contracts |
| [roles.md](./roles.md) ([ru](./roles.ru.md)) | AI and human authority boundaries |
| [using.md](./using.md) ([ru](./using.ru.md)) | Installation and product integration |
| [contracts/board-snapshot.md](./contracts/board-snapshot.md) ([ru](./contracts/board-snapshot.ru.md)) | Read-only board snapshot for fuse-map (`schema_version: 1`) |

Executable Thinker (LLM) bindings live in `process/skills/**`; the Process machine contract lives in the kernel. Change/artifact schemas live in `process/schemas/**`. The board snapshot schema is a **tool compatibility** contract under `docs/contracts/`, not a product artifact schema; do not copy it into consuming products.

