# DeltaFuse Process

[**English**](README.md) | [Русский](README.ru.md)

DeltaFuse is a context-sliced, specification-driven workflow that turns raw intent into verified code through small, strictly bounded contexts.

Two runtime roles stay distinct: **Core** (enforces the Process) and **Worker** (LLM or human who writes Change files). The Process itself is the lifecycle in [workflow.md](./workflow.md). See [core-and-worker.md](./core-and-worker.md).

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
├── AGENTS.md                  # optional, host-owned
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
| [core-and-worker.md](./core-and-worker.md) ([ru](./core-and-worker.ru.md)) | Core vs Worker; Process is the lifecycle, not a role |
| [workflow.md](./workflow.md) ([ru](./workflow.ru.md)) | Lifecycle, gates, bugs, Bootstrap, and convergence |
| [state-machine.md](./state-machine.md) ([ru](./state-machine.ru.md)) | Change, slice, task, and Decision states |
| [small-llm-contract.md](./small-llm-contract.md) ([ru](./small-llm-contract.ru.md)) | Small-LLM Quality Contract: reference Worker <=40B, dense or MoE (qwen3.8-27b), 128k window, 64k/24 framework budget (V3-FIX-020) |
| [context-model.md](./context-model.md) ([ru](./context-model.ru.md)) | Domain routing, slicing, and context contracts |
| [roles.md](./roles.md) ([ru](./roles.ru.md)) | AI and human authority boundaries |
| [using.md](./using.md) ([ru](./using.ru.md)) | Installation and product integration |
| [bench.md](./bench.md) ([ru](./bench.ru.md)) | Agent-agnostic Worker bench (`deltafuse bench`); Core scores the disk |
| [contracts/board-snapshot.md](./contracts/board-snapshot.md) ([ru](./contracts/board-snapshot.ru.md)) | Read-only board snapshot for fuse-map (`schema_version: 1`) |
| [contracts/halt.md](./contracts/halt.md) ([ru](./contracts/halt.ru.md)) | Host buttons for `next --json` halt (`kind` + `choices`) |
| [contracts/leash.md](./contracts/leash.md) ([ru](./contracts/leash.ru.md)) | Write envelope for `next --json` and `deltafuse leash` |

Executable Worker (LLM) bindings live in `process/skills/**`; the Core machine contract lives in the kernel. Change/artifact schemas live in `process/schemas/**`. Board snapshot, halt, and leash schemas are **tool compatibility** contracts under `docs/contracts/`, not product artifact schemas; do not copy them into consuming products.
