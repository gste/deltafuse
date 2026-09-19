# Integrating DeltaFuse

[**English**](using.md) | [Русский](using.ru.md)

DeltaFuse is installed as a versioned external framework. The product repository stores product state and a thin integration layer, but never a copy of canonical process documentation.

## Install

> **DF3-005**: two supported channels — nested source checkout (`vendor/deltafuse`) or a wheel. The wheel ships the immutable runtime asset bundle (schemas, templates, skills) and needs no source checkout. Scaffold new Changes with `deltafuse new <change-id> --route code|docs|ops` — it never closes Intake. Upgrades fail closed while active Changes exist; evidence stamps are never re-signed.

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
docs/intake/
docs/changes/
docs/spec/
docs/decisions/
docs/archive/intake/
docs/archive/changes/
```

It also installs adapter skills in `.agents/skills/`, `.cursor/skills/`, and `.gemini/skills/`. `adapters.mode` is `auto` (default), `link`, or `copy`.

### Host instructions

`AGENTS.md` and `AGENTS.override.md` are host-owned optional integration surfaces. DeltaFuse never creates or changes either by default. In an interactive terminal, `init` asks how to integrate; in CI/non-interactive use it preserves both files and reports that `/run` or `deltafuse next --json` is the explicit activation path. Choose deterministically with `--agents-md=bridge|preserve|replace`. `bridge` appends one small marked bridge to the effective file (`AGENTS.override.md` takes precedence); `replace` replaces that existing effective file and requires an interactive second confirmation. The full Worker contract stays in generated `run` and lifecycle skills.

- **link** when the framework checkout lives inside the product (git submodule or vendor path, recommended `vendor/deltafuse`): each adapter skill is a relative symlink to `process/skills/<name>`. Cursor sees live skills after `git submodule update`. `init --force` only refreshes `.deltafuse/lock.yaml`. Do not commit the adapter links. On Windows without symlink privilege the installer may create a directory junction instead (absolute, machine-local).
- **copy** otherwise, and when the OS refuses symlinks: stamped snapshots marked `DO NOT EDIT`, with version, source URI, and content hash.

The installer does not create `docs/process/`, `docs/init/`, or `docs/todo/` in the product repository.

## Pinning and upgrades

Anything the Core owns uses the token `deltafuse` (no hyphen): the CLI, the Python package, the product pin `.deltafuse/`, and the git slug (`gste/deltafuse`). Nest the framework checkout at `vendor/deltafuse` so clone path and `lock.yaml` `source` match. Do not put the submodule in `.deltafuse/` — that directory is the pin, not the checkout.

```bash
git submodule add https://github.com/gste/deltafuse.git vendor/deltafuse
```

`.deltafuse/config.yaml` specifies the requested framework version and repository settings, including `workflow.call_width` (`narrow` | `medium` | `wide`, default `wide`). `.deltafuse/lock.yaml` pins the resolved version, schema version, framework content hash, and the Analyze call-width profile. Re-run the installer after changing `call_width` so lock matches config.

For framework releases, `VERSION` is the single machine-readable version source. Package metadata reads it dynamically, and installer templates contain a schema-valid `0.0.0` marker that each installer replaces from `VERSION`. A version bump therefore edits `VERSION` plus the human release entry in `CHANGELOG.md`; generated assets are synchronized without embedding the release number.

Re-running the installer with `-Force` (PowerShell) or `--force` (Bash) performs an explicit framework upgrade. It updates the requested version in config and lock. Linked adapters follow the nested checkout; copied adapters are regenerated. Product-owned specification, Changes, Decisions, host instruction files, and existing templates stay. Before updating lock:

1. Review active Changes and their recorded framework/schema versions.
2. Complete them on the current version or explicitly close the Change.
3. Re-run the installer and validate product layout.

Never edit adapter skills (copied snapshots or the canonical files they link to) or create a local process fork. Product-specific routing and repository conventions belong in `.deltafuse/config.yaml` and, if the host chooses one, its own concise `AGENTS.md`.

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

Import/syntax failures and `_`-prefixed Red tests are not authentic. The Core stamps the YAML; `check-gate --gate declaring` rejects a schema-valid file that was not written by `deltafuse evidence`.

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

`deltafuse next --json` `envelope` is the allow-list of paths the Worker may write ([leash.md](./contracts/leash.md)). The host MUST restrict write-tools to `envelope.write`. If it cannot, `/run` still calls `deltafuse leash` before leaving the step (not a substitute for the git hook). `deltafuse leash` compares the git diff (or `--file`) to ready envelopes. Intake must not write `src/**`. A null envelope plus a dirty `src/**` / `tests/**` is an orphan and fails. When `halt.kind` is `decision` or `spec`, `envelope` is null and product-code write tools stay off. `docs/spec/**` is an orphan only after `project.baseline: accepted`. `docs/intake/**` and `AGENTS.md` are not orphans. `workflow.leash: advisory` reports the same violations and exits 0. `enforce` installs a git hook and (optional) CI job; `off` does not. Fuse-map UI and Cursor buttons live outside `src/deltafuse/**`.

```text
deltafuse leash <product-root>
deltafuse leash <product-root> --file src/foo.py
```

## Artifact Writer

Core provides a schema-driven serialization and validation service for Change package artifacts ([artifact-writer.md](./contracts/artifact-writer.md)).

### Practical Usage & Examples

```text
# Detect capabilities and schemas supported by the installed writer
deltafuse artifact describe --kind task --operation create

# Create a new Change artifact via JSON payload
deltafuse artifact create --kind task --change docs/changes/CHG-101 --input input.json

# Update an existing artifact atomically using JSON Pointer patch with target SHA assertion
deltafuse artifact update --kind task --change docs/changes/CHG-101 --target tasks/TASK-001.md --expected-sha256 <sha> --input patch.json

# Perform a read-only schema and reference validation pass without modifying files
deltafuse artifact validate --kind task --change docs/changes/CHG-101 --target tasks/TASK-001.md --json

# Update parent Change child index after adding or updating a task/slice
deltafuse artifact update-index --change docs/changes/CHG-101 --child-kind task --child-id TASK-001
```

### Capability Detection & Compatibility
Clients detect Artifact Writer availability using `deltafuse artifact describe --kind <kind> --operation <op>`. If the subcommand is unavailable or returns unsupported kind errors, clients fall back to manual frontmatter authoring.

### Manual Authoring Fallback & Legacy Artifacts
Manual YAML/frontmatter authoring remains fully valid and supported. Existing artifacts are never automatically rewritten or bulk-migrated. The Artifact Writer reads legacy and manually authored artifacts seamlessly.

### Canonicalization Opt-in
To reformat or normalize metadata on existing noncanonical artifacts, an explicit `--canonicalize-metadata` opt-in is required alongside expected target hash verification. Noncanonical metadata will not be reformatted without explicit consent.

### Transaction Recovery Procedure
In the event of process interruption during creation or update operations, the Core checks `.deltafuse/journal/` under `ProductMutationLock`. Pending transactions marked `prepared` are restored to their previous target state, while transactions marked `published` complete receipt finalization and output publication cleanly.



## External boards

A read-only UI (fuse-map) must consume the [board snapshot contract](./contracts/board-snapshot.md) for both cards and board layout (columns + steps). It must not parse `docs/changes/**` or hardcode the lifecycle. The installer does not copy `docs/contracts/**` into the product. Fuse-map pins `schema_version` in its own repository. This framework does not ship a board UI.

```text
deltafuse board <product-root> --json
deltafuse board <product-root> --json --archive
```

Stdout is one JSON object. No product files are written. Missing `.deltafuse/lock.yaml` is a hard error, not an empty board.


## Recovery

- A Change stuck mid-transition: run `deltafuse advance <change> --gate <gate>` again — the last receipt is authoritative and the pending status write is completed.
- A status that disagrees with the last receipt halts the queue: close or migrate the Change, or hand the artifact back to Core via `advance`. Hand edits are never migrated.
- Artifacts from unsupported schema versions stop with a `schema_version` diagnostic and are left untouched; migrate them manually to v3.
- Artifact versioning (V3-FIX-013): `change`, `evidence`, and the capability catalog carry an explicit `schema_version: 3`. Change-nested artifacts (`tasks/**`, `slices/**`, `decisions/**`, `spec-delta` frontmatter, `routing.yaml`, `coverage.yaml`) inherit the schema version of their parent Change artifact — they carry no version of their own and are validated fail-closed through the Change contract.
- Verify the whole product contract any time with `deltafuse validate-config .`.
- Human Gate clicks live in `.deltafuse/gate-journal.jsonl` (Core-owned): rebuilds are detected; in `broker-signed` profile only broker-signed receipts validate.
