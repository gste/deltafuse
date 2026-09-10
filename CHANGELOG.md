# Changelog

All notable changes to the DeltaFuse framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `deltafuse bench` prepares an agent-agnostic Worker sandbox (`M01-cooldown`) and scores each lifecycle step from a judge pack. No LLM call. `bench score` requires `--pack` or `DELTAFUSE_BENCH_PACK` and will not write a scorecard into the sandbox.

## [2.3.0] - 2026-09-10

### Added

- `deltafuse evidence` runs a product command and writes `evidence/red|green|regression` YAML. Workers do not hand-write exit codes or `failure_category`.
- `deltafuse next` selects the first ready lifecycle step (and `--list` prints the derived work queue). Slash commands without a Change id ask the kernel.
- `deltafuse next --human` prints a checklist from the step contract so a person fills the same Change files (`check-gate`, `evidence`).
- Lifecycle skills bind the Worker (LLM): write artifacts, `check-gate`, then `deltafuse next`. They do not pick the next slash command.
- Named **Core** vs **Worker**. **Process** is the lifecycle, not a runtime role. Human Gates are Process stops, not Worker steps. See `docs/core-and-worker.md`.
- `deltafuse board --json` emits a read-only fuse-map snapshot (`layout` + Change cards). No product writes, no `check-gate` fan-out.
- `deltafuse next` names one Analyze pass (`routing` | one capability `slice` | `coverage`). `analyzed` requires a slice per routing primary capability.
- `deltafuse coverage` writes `coverage.yaml` from routing and slice frontmatter. Workers do not hand-write it. Unknown top-level coverage keys are ignored.
- `deltafuse next` names one Specify slice (`spec_refs` only). `specified` rejects spec-delta paths outside those files.

### Fixed

- `targeting` rejects code-route Red `expected-failure` unless `failure_category` is `behavioral-mismatch` (TEST-004).

## [2.2.0] - 2026-09-10

### Changed

- Lifecycle skills and slash commands are one word: `/intake`, `/analyze`, `/specify`, `/decompose`, `/declare`, `/implement`, `/verify`.
- Renamed the Target step to **Declare**: freeze a Red oracle that states what must become true before Implement. Re-run the installer to regenerate product skill snapshots.

### Added

- Read-only board snapshot contract for fuse-map (`docs/contracts/board-snapshot.md`), including required `layout`.
- Change `route` values `docs` and `ops` (file or schema oracles instead of product pytest).
- Analyze `workflow.call_width` (`narrow` | `medium` | `wide`).

### Fixed

- Specify requires live `docs/spec/**`; `spec-delta.md` alone does not close the gate.
- Task `context_budget` and `PHASE_CONTRACTS` write globs are enforced at FSM gates.

## [2.0.0] - 2026-09-04

### Breaking

- Replaced the four mixed lifecycle skills with seven context-bounded primitives: `/intake`, `/analyze-change`, `/specify-change`, `/decompose-change`, `/target-task`, `/implement-task`, and `/verify-change`.
- Replaced product `docs/inbox/`, `docs/todo/`, and `docs/init/` with `docs/intake/`, Change-owned `docs/changes/<change-id>/tasks/`, and `.deltafuse/config.yaml` baseline state.
- Stopped copying canonical `docs/process/**` into product repositories; products now pin the external framework in `.deltafuse/config.yaml` and `.deltafuse/lock.yaml`.
- Generalized architecture-only ADRs into product, architecture, integration, policy, and operational Decision records with explicit lifecycle status.

### Added

- Typed slice-level Delta projections, capability routing, context budgets, Decision convergence, and cross-artifact verification.
- Version/hash-stamped generated agent adapters for Cursor, Gemini, and universal agent discovery.
- Schemas for Change, capability, Decision, task, and evidence artifacts.
- Product layout validators and Change templates.

### Changed

- Split TDD into Target/Red and Implement/Green operations while retaining executable evidence.
- Preserve completed tasks and evidence inside the archived Change package.
- Formalized `/bootstrap`, `/change`, and `/fix-bug` as workflow Execution Profiles (`docs/roles.md`) composed of canonical primitives rather than monolithic wrapper skills, preserving strict Human Gate boundaries and verifiable evidence at each step.

## [1.2.0] - 2026-09-04

### Added

- Unified ingestion directory `docs/inbox/` (and `docs/archive/inbox/`) as the single entry point for all raw external inputs.
- Streamlined 4-skill suite:
  - `/triage` (`01-triage.md`): Universal intake, Stop-and-Ask analysis, and triage into spec/ADR/tasks.
  - `/audit-spec` (`02-audit-spec.md`): Specification consistency, ADR mirroring, and coverage validation.
  - `/plan-story` (`03-plan-story.md`): Modular specification and spec git diff slicing into atomic tasks.
  - `/implement-task` (`04-implement-task.md`): Universal TDD task execution engine.
- Native skill registration for Google Antigravity / Gemini CLI (`.gemini/skills/`).

### Changed

- Replaced fragmented intake and execution commands with 4 orthogonal skills.
- Unified `docs/todo/<story>/` into single flat task queue (`NN-<slug>.md`).
- Streamlined ADR template to binary `accepted: false/true` status with inlined pros & cons.

## [1.0.0] - 2026-09-03

### Added
- Initial extracted DeltaFuse Specification-Driven AI Engineering Framework.
