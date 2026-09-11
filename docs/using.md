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

It also installs adapter skills in `.agents/skills/`, `.cursor/skills/`, and `.gemini/skills/`. `adapters.mode` is `auto` (default), `link`, or `copy`.

- **link** when the framework checkout lives inside the product (git submodule or vendor path): each adapter skill is a relative symlink to `process/skills/<name>`. Cursor sees live skills after `git submodule update`. `init --force` only refreshes `.deltafuse/lock.yaml`. Do not commit the adapter links. On Windows without symlink privilege the installer may create a directory junction instead (absolute, machine-local).
- **copy** otherwise, and when the OS refuses symlinks: stamped snapshots marked `DO NOT EDIT`, with version, source URI, and content hash.

The installer does not create `docs/process/`, `docs/init/`, or `docs/todo/` in the product repository.

## Pinning and upgrades

`.deltafuse/config.yaml` specifies the requested framework version and repository settings, including `workflow.call_width` (`narrow` | `medium` | `wide`, default `wide`). `.deltafuse/lock.yaml` pins the resolved version, schema version, framework content hash, and the Analyze call-width profile. Re-run the installer after changing `call_width` so lock matches config.

Re-running the installer with `-Force` (PowerShell) or `--force` (Bash) performs an explicit framework upgrade. It updates the requested version in config and lock. Linked adapters follow the nested checkout; copied adapters are regenerated. Product-owned specification, Changes, Decisions, `AGENTS.md`, and existing templates stay. Before updating lock:

1. Review active Changes and their recorded framework/schema versions.
2. Complete them on the current version or explicitly close the Change.
3. Re-run the installer and validate product layout.

Never edit adapter skills (copied snapshots or the canonical files they link to) or create a local process fork. Product-specific routing and repository conventions belong in `.deltafuse/config.yaml` and the product's concise `AGENTS.md`.

## First operation

| Product state | Operation |
|---|---|
| No accepted specification baseline | Set `project.baseline: draft`, run `/intake`, then perform Bootstrap via Analyze and Specify |
| Accepted specification exists | Set `project.baseline: accepted`, create Changes via `/intake` |

The initial capability catalog is proposed by AI and accepted by a human. After acceptance, capability changes require explicit catalog deltas.

Fresh `init` sets `workflow.leash: off` so a pet can brainstorm. After `project.baseline: accepted`, set `workflow.leash: enforce` and re-run the installer (`deltafuse init --force`). That writes a local git `pre-commit` hook that runs `deltafuse leash` even if the Worker never types the command. A GitHub Action template (`.github/workflows/deltafuse-leash.yml`) is copied once and is optional. per-ankh and fuse-map turn `enforce` on themselves. `advisory` still runs the hook; the commit is not blocked. `off` means no hook; invoking `deltafuse leash` still fails on violations.

## Kernel evidence

The Worker writes tests and production files. The Core records proof:

```text
deltafuse evidence <change-dir> --phase red --task TASK-001 --changed-path tests/test_foo.py -- pytest tests/test_foo.py -q
```

Import/syntax failures and `_`-prefixed Red tests are not authentic. `check-gate --gate targeting` still enforces the YAML on disk.

## Kernel coverage

After routing and one slice per primary capability, the Core writes the claim matrix. Workers do not hand-write `coverage.yaml`:

```text
deltafuse coverage <change-dir>
```

Then `check-gate --gate analyzed`. Re-running keeps existing `tasks` / `evidence` / `status`.

## Specify one slice

After Analyze, `deltafuse next --step specify` names one unspecified slice. Write only that slice's `spec_refs`. Do not load the whole `docs/spec/**` tree. When every slice is `specified`, `specify_pass` is `close`: `check-gate --gate specified`. Do not close the Change gate mid-set.

## Next work

Do not pass a Change id unless you mean a specific package. The Core picks the first ready item:

```text
deltafuse next
deltafuse next --list
deltafuse next --human
deltafuse next --step declare --json
deltafuse decide <change-dir> --decision DEC-0001 --status accepted
deltafuse decide <change-dir> --spec --status accepted
```

`--human` is the same step for a human Worker: read/write globs, `evidence` where needed, then `check-gate`. Not a second process. `deltafuse decide` is the only writer of DEC/spec `accepted` or `rejected`; editing frontmatter does not close the Human Gate.

Default LLM entry is `/run` (through-mode): `deltafuse next`, load that skill, continue in the same session. Do not wait for pasted `/analyze` … `/verify`. When `next --json` has `halt.kind` `decision` or `spec`, present `halt.choices` as host buttons from the [halt contract](./contracts/halt.md), wait, then run only `choice.command`. `inspect` (`command: null`) means stop. Single-step skills restart one step after a problem.

Generated skills bind the Worker to an LLM. They write Change files, close with `check-gate`, then run `deltafuse next` in this same session. They do not pick the next slash command.

Empty ready queue exits non-zero and prints blocked items (DEC, spec gate) plus `halt.choices`, or a `done` halt when there is no new intake.

## Worker bench

Install a product sandbox, let any Worker fill it, then score **from a judge host** that has the pack. The Core does not call a model. The Worker must not run `bench score`. Attempts come from the Core journal, not from the Worker.

```text
deltafuse bench init M02-policy-stats <product-dir>
deltafuse bench journal <product-dir>
deltafuse bench score <product-dir> --pack <framework-or-pack> --json --label cursor+opus-5 --out-file ../scores/opus.json
deltafuse bench compare ../scores/opus.json ../scores/flash.json
```

See [bench.md](./bench.md). Oracle and hidden tests stay in the framework pack.

## Host halt

`deltafuse next --json` `halt` is the host button contract ([halt.md](./contracts/halt.md)). Render every `choices[].label`. Run only `choice.command` from the product root. `inspect` (`command: null`) means stop. Do not add merge or `git push` buttons. Core does not draw UI.

## Write envelope

`deltafuse next --json` `envelope` is the allow-list of paths the Worker may write ([leash.md](./contracts/leash.md)). `deltafuse leash` compares the git diff (or `--file`) to ready envelopes. Intake must not write `src/**`. A null envelope plus a dirty `src/**` / `tests/**` is an orphan and fails. `docs/spec/**` is an orphan only after `project.baseline: accepted`. `docs/intake/**` and `AGENTS.md` are not orphans. `workflow.leash: advisory` reports the same violations and exits 0. `enforce` installs a git hook and (optional) CI job; `off` does not.

```text
deltafuse leash <product-root>
deltafuse leash <product-root> --file src/foo.py
```

## External boards

A read-only UI (fuse-map) must consume the [board snapshot contract](./contracts/board-snapshot.md) for both cards and board layout (columns + steps). It must not parse `docs/changes/**` or hardcode the lifecycle. The installer does not copy `docs/contracts/**` into the product. Fuse-map pins `schema_version` in its own repository. This framework does not ship a board UI.

```text
deltafuse board <product-root> --json
deltafuse board <product-root> --json --archive
```

Stdout is one JSON object. No product files are written. Missing `.deltafuse/lock.yaml` is a hard error, not an empty board.
