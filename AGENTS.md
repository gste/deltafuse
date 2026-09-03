# AGENTS.md

Instructions for autonomous AI agents and AI CLI tools (Cursor, Google Antigravity, Claude Code, Copilot, etc.).

## One-line mandate

The active specification pack under `docs/spec/` is the **only implementation law**. If code and spec disagree, the specification wins. Implement from `docs/spec/` and task files under `docs/todo/`, never from chat history, raw intake files, archives, or ADR text alone.

## Repository layout (quick index)

| Topic | Source of truth |
|---|---|
| What to build / change | `docs/spec/**` (the Specification pack) |
| Why a decision was made | `docs/decisions/**` |
| How we work | DeltaFuse: `docs/process/**` + this file |
| Current story tasks | `docs/todo/<story>/NN-<slug>.md` |
| Raw intake / dumps | `docs/inbox/` (for `/triage`) |
| Processed archive | `docs/archive/inbox/` |

## 4 Core Agent Skills

| Skill | Role | Purpose |
|---|---|---|
| `/triage [path/text]` | Auditor / Triage | Universal intake: processes chat input or files from `docs/inbox/`, clarifies ambiguities, compiles spec/ADR or outputs atomic task `docs/todo/<story>/NN-<slug>.md`, and archives input to `docs/archive/inbox/`. |
| `/audit-spec` | Auditor | Audits spec consistency, mirrors accepted ADRs into `docs/spec/`, checks coverage matrix. |
| `/plan-story` | Planner | Slices an accepted spec module or `git diff -- docs/spec/` into atomic tasks in `docs/todo/<story>/NN-<slug>.md`. |
| `/implement-task <path>` | Implementer | Universal TDD engine: implements any task from `docs/todo/<story>/NN-<slug>.md` (failing test -> code -> closes task -> updates CHANGELOG). |

## Hard prohibitions

- Do not invent requirements missing from `docs/spec/`.
- Do not implement from chat history, raw intake files in `docs/inbox/`, archive, or ADR text alone.
- Do not expand scope beyond what the active Specification states as in-scope.
- Do not log or commit secrets, tokens, or raw credential files.
- **ABSOLUTE PROHIBITION:** Never execute `git push` under any circumstances (to any remote or branch). Pushing to remote is strictly Human-Only.
- Never execute destructive git commands (`git push --force`, `git reset --hard`, `git clean -f`).
- Do not change `docs/spec/**` or `docs/decisions/**` unless the task explicitly allows it.
- Do not edit spec anchors outside the declared Spec delta.
- Do not accept ADRs (`accepted: true`).

## PR expectations

- Prefer one task ≈ one PR.
- The implementing PR deletes the closed task file in `docs/todo/<story>/`, appends Closed in `docs/todo/README.md`, adds a `CHANGELOG.md` Unreleased bullet, and removes the story README row; delete `docs/todo/<story>/` if nothing remains.
- No drive-by refactors outside task scope.
- `docs/spec/**` changed ⇒ PR body carries the Spec delta (`ADDED` / `MODIFIED` / `REMOVED` + anchors) and the diff stays inside it.