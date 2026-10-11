# Changelog

All notable changes to the DeltaFuse framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Reopening a task puts its product files back as the `declaring` gate found them.** In the
  reference run ref-m04-363-2 (qwen3.8-27b, M04, 2026-10-11) the Worker wrote TASK-002 to the
  accepted spec in Implement, proved four of its own frozen tests contradictory and blocked the
  task, leaving the code in place. Reopening archived the Red but not the code, so the corrected
  oracle passed on it: Red `already-green` for a task promising a delta, a second halt on the same
  task, and the run ended - the Worker had done right. The `declaring` gate (every Red taken, no
  task implemented) now copies each live task's product files (its listed `allowed_paths` outside
  Declare's test globs, stubs included) to `.deltafuse/snapshots/<change>/` and records their
  digests in its transition receipt (`product_snapshot`); `decide --status reopened` restores the
  task's files to those copies, refuses when a copy no longer matches its digest, and names the
  restored files in `reopen.yaml` and the next declare step. A sibling that changed the same file
  loses that change too; its evidence goes stale and the queue sends it back to Implement (owner
  decision 2026-10-11). docs/workflow and docs/state-machine (en, ru) and the declare skill say so.

- **Decompose says what `requirement_delta` means for a task that guards existing behavior.** In
  the reference runs on M03 (qwen3.8-27b, 2026-10-08) the backward-compatibility claim (CR-009, a
  `constraint`) became a guard task whose test passes on unchanged code. In ref-m03-351 the reference
  labeled it `none`, the Core closed it as `superseded` and the run passed; in ref-m03-356 it labeled
  the same task `added`, and the already-green Red of a task promising a delta halted the run for the
  human (owner rule 2026-10-04). The decompose skill now says the field names a change in behavior: a
  task that only guards behavior the product already has is `none`, even when the Change writes that
  requirement down for the first time. No Core rule changed.

- **The human can reopen a blocked task for Declare.** In the reference run ref-m01-352
  (qwen3.8-27b, M01, 2026-10-08) the Worker declared a Red test no code could pass (a 10 s penalty
  still asserted at t=100), found it in Implement and marked the task blocked, as the skill says.
  The human's only answer was `--status cancelled`, which dropped the task's whole promise - the
  Change then closed with nothing implemented. `deltafuse decide <change-dir> --task <id> --status
  reopened [--note "<why>"]` now moves the task's Red/Green/regression records to
  `reopened/<task>.<n>/` (outside `evidence/`, with the note in `reopen.yaml`), returns it to
  `pending` and journals a `task` gate receipt `reopened`. That task alone may then be declared
  again while its Change is `declared` or `implementing`; a new Red freezes the corrected oracle,
  and Red is still refused once it is declared. Leaving `blocked` is the human's in both ways:
  `deltafuse state` refuses it and names both commands, as does the `blocked` halt. The declare
  skill says how to take a reopened task; docs/workflow and docs/state-machine (en, ru) describe it.
  The leash takes the archive (for a task the journal says was reopened) as the human's write,
  and the reopened task's new Red record as the Core's, so the `implemented` gate names neither.

- **`coverage.yaml` carries the Core's evidence summary per task, and Verify reads it.** In the
  reference run ref-m03-347 (qwen3.8-27b, M03, 2026-10-07) the verify skill already said the Core
  had checked the evidence, and the reference still opened every Red/Green/regression record and
  task file to see for itself: 25 files in one call, against the bench's bounded-reads threshold
  of 24, growing with the number of tasks. The Core now writes `task_evidence` into
  `coverage.yaml` - per task its status, Red result, Green result, whether regression is on the
  current tree, and `problems` from the same checks the `implemented` gate makes - and refreshes
  it at the `implemented` gate as well as `analyzed` and `converged`. The verify skill takes the
  evidence from there and opens a record only when its `problems` or a gate error names it;
  `coverage.schema.yaml` and `docs/workflow(.ru).md` describe the field. No check moved.

- **`deltafuse next` names no ready step when no intake is waiting.** After the archive in the
  reference run ref-m03-347 (qwen3.8-27b, M03, 2026-10-07), `next --json` returned a ready
  `intake` step (`intake_pending: false`) next to a `done` halt. The verify skill says to execute
  the ready step `next` names, and the reference opened CHG-002 from the request CHG-001 had just
  delivered. With no intake file waiting and no step asked for, `selected` is now `null` and the
  `done` halt says not to start a Change the human has not stated; `next --step intake` still
  names it, and the exit code is unchanged.

- **A superseded task has no Green, and a stray one does not block the `implemented` gate.** In
  the reference run ref-m03-346 (qwen3.8-27b, M03, 2026-10-07) a task correctly superseded on
  an already-green Red later got a Green record anyway; `deltafuse evidence` accepted it, and the
  `implemented` gate then refused it as "answers an already-green Red" with every task done - no
  step could clear it, and the run stalled. The gate now skips the Green of superseded and
  cancelled tasks, and `deltafuse evidence --phase green` refuses for such a task, saying its
  test stays as regression.

- **A delta task must be able to turn its own Red green.** In the reference run ref-m03-345
  (qwen3.8-27b, M03, 2026-10-07) Decompose split "write the tests" (TASK-001: `allowed_paths`
  tests only, `src/**` forbidden) from "implement" (TASK-002, depending on TASK-001). TASK-001
  ran first and its Red could never pass inside its own envelope; the reference proved it and
  halted. An older run (c336b-m01) closed the same split only by writing `src/` outside the
  task's `allowed_paths`. The `decomposed` gate now refuses, on the `code` route, a task with a
  requirement delta that may change no product file and depends on no task that may; the
  decompose skill says so. Over the 107 Changes of the bench runs to date it flags 5, each such
  a split or a delta task with no paths at all.

- **Blocked is judged on the oracle as declared.** In the Gemma 31B shakedown cls-g31-m03
  (M03, 2026-10-06) the Worker rewrote a frozen test, Green was refused for it, and the task was
  then marked `blocked` as an "oracle mismatch" - a halt that read to the human as a declared
  oracle no code can pass. `deltafuse state --status blocked` is now refused while the task's
  frozen oracle is changed, naming the change; the implement skill says so.

- **Verify reads the Core's trace instead of every evidence record.** In the reference run
  ref-m02-341 (qwen3.8-27b, M02, 2026-10-05) the verify step held 30 files in one call - 15 of
  them Red/Green/regression records, 5 task files - because the verify skill asked the Worker
  to "confirm valid Red/Green evidence, scoped regressions, allowed paths, and no test-oracle
  weakening" by hand: checks the Core had already made at the `implemented` gate and makes again
  at `converged`. The step's context grew with the number of tasks and broke the bench's
  bounded-reads threshold (24 files). The skill now reads the trace from `coverage.yaml` and
  opens an evidence record, task file or source artifact only when a gate error names it or for
  a gap it found; `docs/workflow(.ru).md` say the same. No check moved or weakened.

- **Red is not taken again after Declare.** In the Gemma 31B shakedown cls-g31s5-m02 (M02,
  2026-10-05), with its Green refused in Implement ("Green did not turn the Red tests green"),
  the Worker recorded Red for the task again, three times, and each was accepted as authentic:
  a Red retaken there freezes the tests as they are at that moment, so the frozen-oracle check
  no longer guarded the declared oracle. `deltafuse evidence --phase red` now refuses, before
  running anything, a task that is `implementing`, `implemented` or `verified`, or `declared`
  once the Change has left Declare, and names the way out (green and regression, or `blocked`
  when the declared oracle is wrong); the implement skill says the same. While the Change is
  still in Declare a `declared` task may retake Red: the first version of this guard covered
  that too and left the reference run ref-m02-340 no way out of the next defect.

- **A sibling task's Declare stub does not fail another task's Red.** Nothing commits between
  tasks, so the Core-computed `changed_paths` of every later Red carries the stubs earlier
  tasks wrote in their own Declare. In ref-m02-340 (qwen3.8-27b, M02, 2026-10-05) TASK-002's
  stub `src/ratelimit/policy.py` failed the `declaring` gate for TASK-001 and TASK-003 - and,
  told only the path, the reference hand-edited the wrong Red records. A Red's product paths
  may now be any path a task of the Change (not cancelled) declares in `allowed_paths`, and
  the refusal names the record.

- **`deltafuse artifact write --change` takes the Change id as well as its directory.** In
  the Gemma 31B shakedowns cls-g31s-m02 and cls-g31s3-m02 (M02, 2026-10-04/05) the Worker
  passed `CHG-001-ratelimit-stats-policy` instead of `docs/changes/CHG-001-ratelimit-stats-policy`.
  The writer looked for `<product>/CHG-001-.../change.yaml`, answered that `change.yaml`
  "cannot be read", and the Worker - told its Change was broken - rewrote the Core-owned file
  by hand until the run stalled. A bare Change id (or its unique `CHG-NNN` prefix) now resolves
  to the Change directory under the product's changes path. The queue also halts, as for an
  unreadable file, on a `change.yaml` that parses but has no valid Change `id` (the second
  run's hand-written `change: <id>`), instead of selecting analyze while every write is refused.

- **Cancelling a task is the human's decision.** `deltafuse state --task <id> --status
  cancelled` let the Worker drop a pending or declared task with no condition (observation
  from the reference run ref-m02-338, 2026-10-04): a hard task could simply be cancelled, and
  only an independent hidden suite would notice. `deltafuse state` now refuses `cancelled`
  and names both ways out: the Worker marks a task it cannot do `blocked` and stops; the human
  cancels with `deltafuse decide <change-dir> --task <id> --status cancelled`, behind the
  Human Gate password when the product has one, journaled as a `task` gate receipt. A
  `blocked` task can now be cancelled (by the human only); the halts for a blocked task and
  for an already-green Red that promised a delta name the command.

- **Verification runs the whole suite.** In the Gemma 31B shakedown cls-g31p2-m02 (M02,
  2026-10-04) `tests/test_stats.py` still failed, the Worker left it out of the verification
  command, the run exited 0 and the `converged` gate closed: the gate checked only that a
  verification run existed and passed. It now refuses a run that did not pass every test the
  Change's own records name - the Red tests of every task not cancelled, a superseded task's
  passing tests, each regression run's tests - and a run with no runner report. Over the 26
  verification runs of the bench to date it flags that run and one more (a Red test deleted
  before verification, gemma31-335-rep, 2026-09-26) and no other. The verify skill and
  `docs/workflow(.ru).md` say the same.

- **A Red test that fails on an error in its own code is not Red.** In the reference run
  ref-m02-339 (qwen3.8-27b, M02, 2026-10-05) Declare wrote `assert not (new & NETWORKY_MODULES)`
  with `new` a set and `NETWORKY_MODULES` a tuple: `set & tuple` raises TypeError whatever the
  product does. Red was recorded as `behavioral-mismatch` next to five honest failures, the
  oracle was frozen, and Implement could only prove that no code passes it and halt for the
  human. `deltafuse evidence` now reads each failure from the runner's report (pytest) and
  refuses, as `failure_category: test-own-error`, a test whose failure was raised in the test
  file itself and is a NameError/UnboundLocalError, or a TypeError between built-in types on
  a line that names nothing from the product (no product import, nothing assigned from one,
  no fixture argument, no helper of the test module). The refusal names the test and line;
  the declare skill and `docs/workflow.md` say the same. Over every Red report of the bench
  runs to date (628 failed tests) the rule flags exactly this test.

- **A hand-broken `change.yaml` halts the Change instead of reading as "no work".** In the
  Gemma 31B shakedown cls-g31s-m02 (M02, 2026-10-04) the Worker rewrote `change.yaml` with a
  file tool (front-matter delimiters, no `id`). The queue skipped the unreadable package, so
  `deltafuse next` answered "No ready work" with nothing blocked and the run ended as if the
  Change were done. The queue now reports the package as blocked, says why the file cannot be
  read and that the human restores it. `deltafuse artifact write`, refusing for want of a
  Change id, now also says that only the Core writes `change.yaml`: told only "no valid
  Change id", the Worker had rewritten the file by hand six times. In the same run a refusal
  for a field the artifact kind does not take (`Field 'kind' is not an allowed semantic
  field`) was repeated nine times by the Worker; the refusal now lists the allowed fields.

- **A task whose Red is already-green is closed, not declared forever.** In the Gemma 31B
  shakedown cls-g31g-m02b (M02, 2026-10-04) a "verify the architectural constraints" task
  wrote a test that the earlier tasks had already made pass. `deltafuse evidence` recorded
  `already-green` and said to "return this outcome upstream", which named no command;
  `deltafuse state --status already-green` was refused; the queue selected declare for the
  task again, and a new step's conversation no longer had the advice: seven declare steps in
  a row, after which the Worker hand-edited other tasks' Red records. The documented exit
  (close the whole Change as a no-op) would have thrown away six tasks' work. Owner decision
  2026-10-04: a task with `requirement_delta: none` and an already-green Red becomes
  `superseded` (`deltafuse state <change-dir> --task <id> --status superseded`, allowed from
  pending, declaring or declared and only then; its test stays as regression); a task that
  promises a requirement delta halts for the human, who cancels it or has it declared again.
  `deltafuse next` names the command in its reason, `deltafuse evidence` names it in its
  advice, and the declare skill, `docs/state-machine.md` and `docs/workflow.md` say the same.

- **A declared oracle no code can pass stops the task for the human.** In the reference
  run ref-m02-338 (M02, 2026-10-04) the Worker proved during Implement that two of its own
  Red tests for TASK-004 contradicted the accepted spec; the implement skill said to
  "stop and re-declare it", there is no way back from `declared` to Declare (and a
  re-declared Red could not fail on code Implement already changed), and the queue selected
  implement five times until the runner stopped the run. The skill now says to mark the
  task `blocked` (`deltafuse state <change-dir> --task <id> --status blocked`) and say
  why; the blocked halt's reason says the task waits for the human. Owner decision
  2026-10-04.

- **A design_ref written as the string "null" is refused with the fix.** In the Gemma 31B
  shakedown cls-g31p3-m02 (M02, 2026-10-04) the Worker sent `design_ref: "null"` four
  decompose steps running; the refusal said only that the file 'null' does not exist, and
  each new step had lost the previous one's guess at the cause. The value is still refused;
  the message now says a task without a design has `design_ref: null` or none.

### Changed

- `docs/small-llm-contract.md`: the reference is `qwen/qwen3.8-27b` in bf16 at one named
  provider; the route is fixed in the judge's `qualify/thresholds.md` (`reference.route`).

## [3.3.7] - 2026-10-03

### Fixed

- **A requirement id that starts a heading is an anchor, whatever its prefix.** Only
  `REQ-`, `SC-` and `POL-` ids counted, and nothing said so: in run c336f-m23
  (qwen3.8-27b, M02) the Worker numbered two new capabilities' requirements
  `## US-001 ...` and `## RP-001 ...`, every `spec-delta.md` reference was refused 14
  times with "Anchor not found", and the run stalled in Specify after $1.2. Any
  `## ABC-001 ...` heading is now an anchor, and a refused anchor is reported with the
  anchors the file has.
- **The implemented gate checks that Green passed the Red tests.** `green_covers_red` ran
  only when the Green evidence was recorded, and the record was written even when it
  failed, so a Green recorded over a different test closed the gate. 3.3.5's isolated run
  hid this for pytest Reds frozen per test; a JVM Red (frozen per file, no isolated run)
  had nothing else. The gate now reads the Green record's runner report and refuses a
  Green that did not pass every test in its Red's `tests.failed`, or that has no report.
- **The Red record no longer names conftest files that do not exist.** It listed every
  `conftest.py` candidate on the frozen test's path, absent ones with `sha256: null`, and
  the Worker went looking for them: run c336b-m01 (qwen3.8-27b, M01) failed T6 on
  `git ls-files conftest.py tests/conftest.py`, correctness 100. The candidates follow
  from the test's path, so only existing ones are recorded; one that appears later is
  still refused as added.

## [3.3.6] - 2026-09-30

### Added

- **`advance` runs the write leash itself (audit F7).** Nothing in the lifecycle asked whether the
  write envelope had been checked: it was a command the Worker chose to run, or a git hook that
  fires on commit. `deltafuse advance` now checks the diff against the step's envelope before it
  writes the receipt, when `workflow.leash` is `advisory` or `enforce`. Advisory reports the
  violations (in the result, on stderr and in the journal) and the transition still happens;
  enforce refuses it and writes nothing. A product with no git or no commit is reported
  `checked: false` with the reason and is not blocked. A fresh `init` now writes `workflow.leash:
  advisory` (it was `off`); `off` still turns both the check and the hook off. Advisory never blocks a
  commit, including the first one of a product that has no HEAD yet.
- **`dir/*` as a capability code root (q6).** A `code_roots` entry `dir/*` owns the files lying
  directly in `dir`, not its subdirectories, so a directory whose subdirectories belong to another
  capability can give its own files an owner (`markdown/*` beside `markdown/extensions/`). It was
  a no-op before. Ownership, the disjoint-roots rule and the draft-with-inherited-code stop all read
  it; `dir/*` overlaps only the same `dir/*` and a tree root that is `dir` or above it.

- **`next --json` says how the Human Gate is answered.** A decision or spec `halt` now carries
  `human_check` (`none` or `password`). With no Human Gate password the prompt says to show the
  choices as buttons in the chat. With one, `decide` answers only in an interactive terminal, so the
  halt sets `terminal_required` (and `interactive_only` on each choice) and its prompt lists the
  commands for the human to run in a terminal; the run skill stops there instead of offering buttons.
  A `decide` refused for lack of a terminal prints the command to type. Optional properties of halt
  contract v1, no bump.

- **The frozen Red oracle is a test, not a file.** The freeze of the declared
  oracle (`red_oracle`, a hash of whole test files) refused honest edits: a
  regression test added to the Red file, as Implement is allowed to, the second
  task's Red written into the same file, a reformat. Red now records
  `red_oracle_tests` (format 2): each test in `tests.failed` with digests of its
  normalised AST and of what it relies on in its module (class, fixtures,
  helpers, imported names, `pytestmark`, hooks, autouse fixtures), plus every
  `conftest.py` on its path and the other declared modules, whole. A weakened
  assertion, a deleted or renamed test, `skip`/`xfail`, a replaced fixture, an
  edited or added `conftest.py` on the path are still refused, and the refusal
  names the test or the file. Green also runs the frozen tests on their own with
  pytest (`oracle_isolation`), so a new test that patches the product, or `-p
  plugin` on the command line, no longer carries them. Java is frozen per file,
  not per method, until per-method freezing is verified on a real Maven/Gradle
  run. A Red without a runner report keeps `red_oracle` and the old check.

### Changed

- **`workflow.call_width` is retired (audit F14).** Nothing but the board snapshot ever read it, yet
  the Analyze skill and a code comment each spent a sentence saying it changes nothing. It is gone from
  the shipped config, the lock the installer writes, the board snapshot (`product.call_width`), the
  init scripts and the docs. A config or lock that still has it is accepted and ignored, whatever it
  holds: it is no longer validated and the two files are no longer compared on it.
- **A step closes its gate with one call (audit F15).** Skills told the Worker to run `check-gate` and then
  `advance`, but `advance` checks the gate again itself and drops the first verdict, so every step was
  two decisions for one. The skills now say `deltafuse advance <change-dir> --gate <gate>`, which checks
  and stamps in one call and prints the errors on a refusal. `check-gate` stays as the read-only preview.
  The advisory claim-to-test findings of `workflow.trace_claims: warn` are printed by `advance --gate
  converged` now (the Core still records them in `evidence/verification/trace_warnings.yaml`).

### Fixed

- Audit fixes (F1-F13, F16-F18), one commit each with its root cause: `archive` requires the
  `converged` transition, not only the gate's content (F1); an already-green Red cannot carry the
  `implemented` gate (F2); the `converged` gate reads the `Outcome:` verdict of `verification.md` (F3);
  `decide --spec` validates before it records an acceptance (F6); Declare may write the stub its task
  declared, which a compiled-language Red needs (F8); the Artifact Writer accepts a slice citing the
  spec a draft capability promises (F9); proposing a specification no longer waits on a catalog only
  the human can accept (F10); `leash` in a repo with no commits names the missing commit (F11);
  `.deltafuse/bench.yaml` is Core-owned (F13); three skill sentences that read as the opposite of the
  Core's contract are reworded (F16-F18).

## [3.3.5] - 2026-09-27

### Added

- **`workflow.trace_claims: warn` (P12, experiment, default off).** A converged run can
  still miss a claim of the request: M02 on Gemma 31B reached `converged` with Verify
  green at 53.5-56.1, and `CR-006` (`TokenBucketLimiter` must accept `reject_threshold`)
  was routed, sliced and named in a test, yet the limiter took the parameter through a
  `policy=` object instead of directly - six hidden-suite checks failed anyway. With the
  flag set:
  - `declare` asks a test to name the claim it proves, in its own name (`test_cr013_...`)
    or a `# covers: CR-013` comment; `deltafuse coverage` records which claim each test
    proves in `coverage.yaml`'s new `tests` field.
  - `check-gate --gate converged` also checks a claim's shape directly against the
    source (a method/parameter the request puts on a class that does not define, take,
    or assign it, checked by AST against every `*.py` in the product) - naming a test is
    not proof the claim's shape held.
  - Both are advisory: printed to stderr, never in `errors`, never affects the exit
    code. The Core also writes its own findings to
    `evidence/verification/trace_warnings.yaml` at the `converged` transition, so a
    warning that only reached a terminal cannot be silently walked past before archive.
  - `off` (default) costs nothing: no extra read, no extra key, byte-identical
    `coverage.yaml`. There is no `enforce` yet - promoting the warning to an error waits
    on running this across enough models to trust it.
- **Two catalog rules for a repository adopted with Fuse-Back**
  (`backlog/roadmap/q6-fuse-back`, decision 5(a) and 5(b)), and neither is specific
  to it.
  - `deltafuse validate-config` refuses **active capabilities whose `code_roots`
    overlap** (compared as directory prefixes, the way ownership reads them).
    Draft, deprecated and removed capabilities are exempt, so a partial adoption
    is not blocked. The under-routing detector maps a diff to owners through the
    roots and is blind where two active capabilities share one.
  - The `analyzed` gate **stops a Change routed into a draft capability whose
    `code_roots` hold code**, but only once `project.baseline: accepted`: inherited
    behaviour nobody has characterized is not a law yet. A draft with no code
    there is the new capability a Worker proposes in Analyze (q8) and is not
    stopped, and neither is any draft under the Bootstrap baseline. The test is
    code on disk rather than a non-empty list, because a proposal may name the
    directory it means to create.

### Changed

- **An Artifact Writer call leaves a line in the command journal**, refused or not
  (`cmd: artifact`, `sub`, `kind`, `identity`, `ok`, `refusal`, `errors`). `artifact
  write` was invisible to the journal, so no metric could tell a Worker that fought
  the Writer for twenty calls from one that never touched it. The outputs the Worker
  sees are unchanged.
- **A gate that meets a hand-written structural file names that first.** When the
  schema errors are about a routing, spec-delta, slice or task file that no writer
  produced, the first error says so and gives the `artifact write` call that replaces
  it; a `change.yaml` with several schema errors gets the same kind of note.
  glm-4.7-flash wrote these by hand: the leash refused them, the files stayed, and
  every gate answered with their schema errors (39 x 3 `[deltas -> N]`, 34 for routing).
- **A wrong subcommand says what was probably meant.** `deltafuse artifact_write` (the
  host's tool name, 8 times in two runs) answers `Did you mean: deltafuse artifact
  write`; a typo gets the nearest command.
- **The `format_change_required` hint names both ways** to pass `canonicalize_metadata`
  (the input JSON, or the host tool's argument).

### Fixed

- **A task's evidence is judged by its own step when the step moved on.** Green
  evidence written, the gate advanced and the next step selected in one Worker turn,
  `state` called only afterwards: the task file was not dirty, so the receipt chain
  gave the implement step no task, and its evidence was refused as outside the
  verify envelope (3 refusals per Gemma 31B run). A task whose evidence for the step
  is dirty is the step's task too.
- **A draft capability's spec can be cited before Specify writes it.** The
  `analyzed` gate refused every slice, task and `spec-delta.md` that cited the
  spec of a capability proposed with `deltafuse capability propose`, because
  the file does not exist until Specify - a step after that gate. M02 runs 1
  and 3 of 2026-09-24 proposed both drafts correctly and then stalled on this
  until the supervisor stopped them. The file check now accepts the spec
  paths of drafts (anchor included); it comes back in full at `specified`,
  where the human also has to accept the draft (`draft_spec_files`).
- **The recorded Red category follows the runner's report, as the verdict does.**
  3.3.4 judged Red by the runner's report but still wrote `failure_category` from
  substrings in the log, and the `declaring` gate reads that field: 23 of 44 Red
  records whose report said "the tests ran and failed" were recorded
  `fixture-error` (no `assert ` in the log) or `import-error` (a test importing a
  name that does not exist yet fails with `ImportError` in its body) and were
  refused by a gate the Core had just agreed with. The other way round, a log
  mentioning an assertion made a test that never ran read `behavioral-mismatch`.
  With a report, an authentic Red is now recorded `behavioral-mismatch` and an
  inauthentic one never is.
- **A Red test that cannot load says why and what to do.** A test importing a
  module that does not exist yet at the top of its file (`from ratelimit.stats
  import StatsStore`) fails at collection, and the refusal said only "tests could
  not run". gemma-4-31b M02 was refused nine times and answered by creating the
  module in Declare (25 refusals by the leash for product code). The refusal now
  names the cause (the import at module level) and the fix (import inside the test
  function, so it runs and fails there).
- **`coverage` without routing says what comes first.** glm-4.7-flash ran it
  before writing routing 31 times and was told only "routing.yaml is missing";
  the refusal now names the order (routing, slices, then coverage).
- **The Writer's input file has one place, and a refusal says which.** The
  skills said "put the JSON file under `.deltafuse/tmp/`"; a Worker read that as
  inside the Change directory, and the leash, which exempts only the product
  root's `.deltafuse/`, refused it 224 times in two runs (glm-4.7-flash), about
  half of that model's refusals. The analyze, decompose and specify skills now
  say "at the product root (not inside the Change directory)" and the refusal
  says the same. The leash is not loosened.
- **Red refusals say what to do instead of repeating themselves.** In
  gemma-334-probe M01 the Worker put an option of `deltafuse evidence` after
  `--`; the Core ran it as a program, recorded exit 127 as a `fixture-error`,
  and the gate only said the category was wrong. The Worker then edited
  product code to change a category that was its own typo, was refused seven
  times with no hint why, and the supervisor stopped the run. Now: an option
  after `--` is refused before anything runs or is recorded; the `declaring`
  gate quotes the record's own summary and says product code is not the fix
  (a test calling an API that does not exist yet fails with `AttributeError` or
  `TypeError`, and that is a legitimate Red); the write-envelope refusals in
  declare say that the phase writes tests only.
## [3.3.4] - 2026-09-24

### Added

- **A Change that needs a capability the catalog lacks can be analysed**
  (`backlog/roadmap/q8-new-capability/1-DECISION.md`). It could not before:
  routing refuses a name the catalog does not hold, and `docs/spec/**` is
  writable only in Specify - after the `analyzed` gate - so the only legal
  move was to route into a neighbouring capability. M02 run 1 did exactly
  that and failed every downstream check.
  `deltafuse capability propose <domain>.<name> --summary ... --spec ...`
  adds the entry as a `draft`; routing accepts a draft and checks only the
  shape of its spec path, because Specify is what writes that file. The
  `specified` gate refuses to close while a capability the Change routes into
  is still a draft - the human makes it active when accepting the
  specification - and `converged` checks again, which is the catalog rule q6
  was holding.
  The catalog stays the human's file: no phase gets it in its write envelope,
  and the Core's write is vouched for by a `capability-draft` receipt with the
  digest it wrote, the way `deltafuse state` vouches for a status rewrite.

### Changed

- **Red is what the runner reported, not what its log looked like**
  (`backlog/roadmap/q7-red-evidence/1-DECISION.md`). The Core read the log
  for the substring `assert`, so the same `TypeError` was authentic when
  pytest echoed the source line and refused when it did not: the Worker's
  `--tb=` decided whether its evidence counted, and 52 of the 89 evidence
  refusals of 2026-09-23 came from that. The Core now reads the runner's own
  JUnit XML - it adds `--junitxml` for pytest itself, and finds what Surefire,
  Failsafe and Gradle write anyway - and applies one rule in both
  ecosystems: the tests ran and none passed. What kept a test from running
  (compilation, collection, a fixture) is not Red, and the refusal says which
  tests and why. A runner with no report falls back to the old heuristic, and
  the record shows which path gave the verdict.
  **The two ecosystems spell `<error>` differently** - pytest means "never
  ran", Surefire means "ran and threw" - so each has its own adapter and the
  canonical Java red, a stub throwing `UnsupportedOperationException`, is
  authentic.
- **Green must turn the Red tests green.** The evidence record now carries the
  test ids the runner reported, and a Green run is refused when a test the
  Red record listed as failed is still not passing. Nothing checked this
  before: a Red test with a typo and a Green run of another test read as a
  finished task.
- **Declare on a compiled language is two moves.** A test cannot name what
  does not compile, so the stub comes first and Red is taken against it. Said
  in the contract and in the declare skill.

### Added

- **JVM runners in the authorized-runner allowlist.** `mvn`, `mvnw`, `gradle`
  and `gradlew` with a test goal (`test`, `verify`, `check`,
  `integration-test`) are recognised; flags before the goal (`mvn -B test`)
  are fine, and `mvn deploy` is still refused. Until now the list held
  pytest, tox, npm, cargo and go, so a Java product could stamp no evidence
  at all without configuring `workflow.test_commands` by hand.

### Fixed

- **The runner allowlist identifies a runner by its name, not by its path.**
  `D:\proj\.venv\Scripts\pytest.exe` is pytest; the allowlist compared
  `argv[0]` literally and refused it as a substituted runner. Where pytest is
  not on PATH - the normal case in an isolated environment - this took every
  evidence command a run made: 27 of 27 in one isolated M01 run, 13 refusals
  across the runs of 2026-09-23. A `python -c` one-liner is still refused,
  and the full argv stays in the evidence record.
- The unreachable copy of the `code` branch in `runner_is_authorized` is
  gone; it sat after the branch's `return` and could never run.
- A refused Red record says what the Core read: the last error line of the
  output and why it is not a behavioural failure. This was the largest class
  of refusal in those runs (52 of 89) and the only evidence of it was the
  verdict - the log of a refused attempt is never stored.

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
