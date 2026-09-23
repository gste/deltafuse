# Changelog

All notable changes to the DeltaFuse framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.3.3] - 2026-09-23

### Changed

- **The reference Worker class is a model of up to 40B total parameters, dense
  or sparse** (owner decision 2026-09-23, documentation only). The ban on
  sparse/A3B rested on one observation - that such a model does not finish the
  lifecycle - and on 3.2.0 two of them did, with correctness 100 and T10 = 0.
  An MoE model counts by total parameters, not active ones. `qwen/qwen3.8-27b`
  stays the model the qualification verdict is read from.

## [3.3.0] - 2026-09-23

### Removed

- **`deltafuse bench score` and `deltafuse bench compare`.** The judge moved
  to `deltafuse-bench` (`deltafuse-bench score|compare`): a change to the
  judge must not ride in the same commit as a change to the code it judges
  (roadmap: one harness in deltafuse-bench). `deltafuse bench init` and
  `deltafuse bench journal` stay - a product produces its own journal.

### Fixed

- `deltafuse state --change` read the status table backwards, which let a
  Change return to `specification-proposed` from `specified` and reopen a
  Human Gate the human had answered.
- The stale bugfix shortcut `analyzed -> declaring` is gone: no command could
  take it, and it made `declared` formally reachable without decompose.
- A gate refused only because it waits for the human is counted as
  `human_waits`, not as the Worker's retry.
- `next` carries `skill_path`, so a Worker does not guess where its skill
  lives.

## [3.2.1] - 2026-09-23

### Changed

- Bench scoring: a check may be **advisory**. It costs a fixed slice of the
  score (`ADVISORY_PENALTY`, 3 points) and is listed in `advisory_findings`,
  but it does not fail its stage and stays out of correctness. The first one
  is `no.unexpected.decision`: the reference model proposed a well-founded
  Decision on a case that expects none, which cost it correctness and a failed
  stage - two gating thresholds - for reading the request less sharply than it
  deserved (owner decision 2026-09-23).

## [3.2.0] - 2026-09-22

The first version qualified against the dense ≤40B reference Worker
(`qwen/qwen3.8-27b`): two q0 baseline runs converged with correctness 100.
Roadmap: `backlog/roadmap/README.md`.

### Added

- **The Worker writes structure only through the Artifact Writer** (roadmap
  item 1). `deltafuse artifact write --kind K --change DIR --input FILE`
  creates or updates a task, slice, routing, spec-delta, change field or
  Decision from fields plus a prose body. The Core reads the expected sha256
  itself and defaults `context_budget`, the `change.yaml` index, a Decision's
  `DEC-NNNN` id, owner and date; spec-delta lists merge per slice. Skills
  teach Writer inputs instead of frontmatter; intake scaffolds with
  `deltafuse new`.
- The leash accepts `routing.yaml`, `spec-delta.md`, slices, tasks and
  `docs/decisions/DEC-*.md` only when their bytes match a known writer: the
  Writer's receipt, `deltafuse state` (its receipt now records `sha256`) or
  `decide` (gate journal).
- **Code ownership record** (q4 decision D, phase 1): verification evidence
  carries `ownership` - the capabilities a Change's code entered (through the
  catalog's `code_roots`) that routing did not name, unowned paths, and how
  blind the check is. Observed only; the bench reads it as T9.
- **Optional Human Gate password**: `deltafuse gate-password set|clear|status`
  stores a salted PBKDF2-SHA256 hash; `decide` asks for it interactively before
  any write. Receipts record `human_check`.
- Token counts record their mode; `DELTAFUSE_TOKENIZER_REQUIRED` refuses the
  heuristic. The heuristic is `a04-01`: UTF-8 bytes / 3.75. Default
  framework-controlled budget 64,000 tokens / 24 files.
- Schema-driven Artifact Writer: `deltafuse artifact describe|create|update|validate|update-index` CLI subcommands and typed Python `ArtifactService` for schema-valid Change artifact creation and atomic JSON Pointer updates.
- Bounded artifact reader (`strict_read_artifact`), frontmatter/YAML codec with explicit formatting canonicalization opt-in (`canonicalize_metadata`), product mutation locking, durable transaction receipts, and authority policy enforcement.
- Small-model paired evaluation protocol (`evaluate_artifact_writer.py`), independent semantic oracle, and evaluation corpus (`tests/fixtures/artifact_writer_eval/eval_corpus.json`).

### Changed

- Three gate refusals moved from the Worker to the Core (roadmap item 4, gate
  boxes): the `analyzed` and `converged` gates judge the coverage the Core can
  derive and `advance` writes `coverage.yaml`; `deltafuse evidence` without
  `--changed-path` records the Core-computed changed set; the `allowed_paths`
  refusal names the paths the Change may write instead of a slice field that
  does not exist.
- Gates need every task; tasks follow their Change's phase; gates close from
  the resting status; a bugfix goes from `analyzed` to `decomposed`; ops-route
  tasks are not blocked by the default bounds.
- One writer for `transitions.jsonl`; Core status writes journal first; the
  archive and `journal-head` are written atomically; `decide` writes a verdict
  and its receipt together or neither.
- Skills and schema errors name the whole expected shape; a YAML value with
  `': '` gets a hint to quote it; task files are named exactly after their id.
- The qualification judge moved to `deltafuse-bench`.

### Removed

- Integrity profile `broker-signed`: its HMAC secret lived in the repository.
  A config naming it is refused with a pointer to the Human Gate password.

### Fixed

- `decide --spec accepted` goes through `advance_change`; leaving
  `specification-proposed` needs the human's accepted verdict; a malformed
  spec delta stays with the Worker, not the Human Gate.
- The leash judges the Worker's diff, not the Core's own writes, and recognises
  `deltafuse state` rewrites by their receipt.
- A task receipt is never resumed as an advance; asking for the status a task
  already has is not an error; an intake note a Change already took in is not
  pending.
- Remediated review findings across `AW-21` through `AW-36`:
  - `AW-21`: Core authorization context enforcement, target path containment inside `docs/changes/<change_id>/`, and halted stage rejection.
  - `AW-22`: Semantic field omission checks and reference validation against existing slice, spec, and dependency files on disk.
  - `AW-23`: Bounded strict JSON reader enforcing duplicate key rejection at all depths, closed envelope validation, and exit code mapping.
  - `AW-24`: Fail-closed product pin (`.deltafuse/lock.yaml`) verification and raw byte schema hash provenance in durable receipts.
  - `AW-25`: Update transaction idempotency, committed request recognition without `stale_target`, and conflict detection on modified request payloads.
  - `AW-26`: Atomic same-filesystem staging and `fsync` flush for journal/receipt records, fail-closed corrupt journal recovery, and shared `ProductMutationLock` across Core evidence, state, decide, scaffold, and coverage writes.
  - `AW-27`: Mode-disambiguated small-model evaluation harness with independent oracle checking disk state and gate enforcement directly.
  - `AW-28`: Subprocess hard-kill (`proc.kill()`) recovery validation at prepare/publish boundaries, multi-process lock contention, platform security checks, and isolated built-wheel qualification.
  - `AW-29`: Operation-envelope schema packaged in installed asset bundle for isolated wheel execution without checkout fallback.
  - `AW-30`: Live Core-selected work context authorization bound and recomputed under product lock.
  - `AW-31`: Strict product pin and schema hash verification against installed framework assets.
  - `AW-32`: Unified product mutation lock for Writer and Core callers across OS processes.
  - `AW-33`: Post-publication target read-back and strict schema validation before issuing committed receipts.
  - `AW-34`: Explicit slice ownership and prerequisite reference validation against live disk state.
  - `AW-35`: Substring scoring replaced with AW-35 independent semantic and Core gate oracle (`check_gate`).
  - `AW-36` (`AW-36a`, `AW-36b`): Platform qualification completed and paired small-model evaluation executed with `small_model_v1` adapter evidence under independent oracle.
  - `AW-37`: Enforced strict Change ID existence, format pattern (`^CHG-[0-9]{3,}(-[a-z0-9-]+)?$`), exact directory equality (`file_cid == change_id`), and active stage validation.
  - `AW-38`: Enforced strict product lock hash verification (`^sha256:[a-fA-F0-9]{64}$`) rejecting missing or malformed content hashes.
  - `AW-39`: Implemented RFC 6901 JSON pointer unescaping (`~1`, `~0`), unified patch verification across all artifact kinds including YAML routing, and independent typed semantic verification.
  - `AW-40`: Withdrew synthetic/hardcoded model scores, established honest missing endpoint reporting (`unavailable_no_endpoint`, `open_for_AW-20`), and preserved empty-corpus denominator integrity.
  - `AW-41`: Restored packaged-schema removal and byte-corruption probes under isolated installed wheel fixture returning exit code 5 (`asset_resolution_failed`), with honest open blocker recorded for native POSIX / symlink runner.
  - `AW-42`: Reconciled final source and artifact hashes, audited restored test coverage, and established full qualification baseline.
  - `AW-20`: Published open-acceptance reconciliation report honestly documenting completed capabilities alongside live model and platform prerequisites.
  - `AW-43`: Reconciled literal acceptance criteria across `AW-37`..`AW-42`/`AW-20` in a verbatim criterion ledger; kept `AW41-R3`, `AW42-R3/R4/F1` and `AW40-F1/F2` execution rows open; superseded unsupported "fully verified/all checks remediated" wording without inventing executions. Reporting card only: acceptance remains open and `AW-40`/`AW-41`/`AW-42`/`AW-20` stay in_progress.


## [3.1.0] - 2026-09-16

### Changed

- Nested framework checkout and git slug are `deltafuse` / `vendor/deltafuse` (same token as `.deltafuse` and the CLI). GitHub is `gste/deltafuse`. Do not put the submodule in `.deltafuse/`.
- Framework version unified to `3.0.0` across `VERSION`, `pyproject.toml`, `__version__`, product templates, and version examples in docs (V3-FIX-003).
- `VERSION` is the single machine-readable release source: package metadata reads it dynamically and installers render schema-valid template markers at install time.
- The installer preserves host-owned `AGENTS.md` and `AGENTS.override.md` by default; explicit bridge, preserve, and replace modes define the optional integration path.
- Framework CI and the copied leash workflow use Node 24-compatible `actions/checkout@v5` and `actions/setup-python@v6`.

## [2.5.0] - 2026-09-11

### Added

- Host halt contract (`docs/contracts/halt.md`): `deltafuse next --json` `halt` is the button list (`kind`, `prompt`, `choices`). Non-null `command` is `deltafuse decide …` only; `inspect` is `command: null`. Bench pack and fuse-map UI stay outside this repository. When `halt.kind` is `decision` or `spec`, `envelope` is null and product-code write tools stay off.
- Write envelope (`docs/contracts/leash.md`) on `next --json` and `deltafuse leash`: git diff (or `--file`) must stay inside a ready `envelope.write`. Hosts MUST restrict write-tools to that list; if they cannot, `/run` still calls `leash`. Intake cannot write `src/**`. Product paths with no covering Change are orphans (`docs/spec/**` only after `project.baseline: accepted`). `workflow.leash: advisory` reports the same violations and exits 0. Fresh `init` writes `leash: off`; `enforce` installs a local git hook and copies an optional GitHub Action.
- Human Gate clicks are journaled by `deltafuse decide` (`.deltafuse/gate-journal.jsonl`). `check-gate` rejects DEC/spec `accepted` or `rejected` written by hand.
- `deltafuse evidence` stamps YAML (`recorded_by` + payload hash). `check-gate` targeting / implemented / converged reject a schema-valid file without that stamp.

### Changed

- First-write YAML matches the schemas: claim IDs are `CR-001` (three digits), routing uses `primary_capability`, `change.yaml` has no `provenance` key, and task `id` is `TASK-001`. `check-gate` names the expected key or pattern when the Worker wrote a close synonym.
- README states who DeltaFuse is for versus a lighter spec-driven kit. Through-mode (`/run`) still stops at Human Gates.

## [2.4.0] - 2026-09-10

### Added

- `deltafuse bench` prepares an agent-agnostic Worker sandbox (`M01-cooldown` floor, `M02-policy-stats` frontier) and scores each lifecycle step from a judge pack. No LLM call. Successful `bench init` prints a copy-paste Worker prompt (`deltafuse next`). `bench score` requires `--pack` or `DELTAFUSE_BENCH_PACK` and will not write a scorecard into the sandbox.
- Bench scorecards report a ranking `score` (`0.6 * correctness + 0.4 * process`) only when the retry journal exists; otherwise `score=n/a`. `correctness` is weighted oracle points (hidden tests split; presence / already-past gates excluded). `M01-cooldown` is a floor; `M02-policy-stats` is the frontier case.
- Bench scorecards report `process` / `efficiency` (check-gate journal) and retry counts. Core appends `.deltafuse/bench-journal.jsonl` for every Core CLI command in a bench sandbox (`check-gate` includes `errors`). `deltafuse bench journal` rolls attempts into cycles. Workers are not asked to log retries.
- Through-mode (`/run`): the LLM Worker follows `deltafuse next` in the same session. `next --json` emits `halt.choices` at Decision and spec Human Gates. `deltafuse decide` records the human click. Merge/`git push` stay Human Gates.
- Adapter skills link into a nested framework checkout (git submodule/vendor) instead of recopying on every `init`. `adapters.mode`: `auto` | `link` | `copy`. Copied snapshots remain the fallback when the framework is not inside the product or the OS refuses symlinks.

### Changed

- `M02-policy-stats` intake now names the public API (`peak_rate`, `token_rejects`, `reject_threshold`, `block_seconds`, `src/ratelimit/stats.py`, `src/ratelimit/policy.py`) so Specify is not a password guess against the hidden suite. Passing judge checks no longer report `detail: missing …`.
- `deltafuse bench init` refuses a non-empty existing directory and prints a recreate command; `--force` / `-f` wipes it and installs a clean sandbox.
- Canonical docs, skills, and templates use one-word lifecycle names (`Analyze`, `Declare`, `Verify`) and slash commands `/intake` `/analyze` `/specify` `/decompose` `/declare` `/implement` `/verify`. Historical changelog entries are unchanged.

### Removed

- Mock `deltafuse eval` (one-shot package dump, `src/deltafuse/evals/**`). Worker scoring is `deltafuse bench`. Analysis experiment snapshots stay in git history (`e3e1149`), not in the working tree.

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
