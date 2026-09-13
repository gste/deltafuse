> Planning handoff: [START-HERE.md](START-HERE.md) and [PLAN.md](PLAN.md).
> The detailed task/interface/scoring documents refine this architectural design.
> Current request is planning only; implementation entry gates apply later.

# J03 Document Flow Benchmark — implementation design

Status: design only; implementation is gated by INSTRUCTION.md section 2.
Target: DeltaFuse 3.0.0. No v2 baseline.
Authority: [INSTRUCTION.md](INSTRUCTION.md).
Observed planning revision: db15ca24cc6af128920165fb7c57d6a18c382978.
The eventual qualification revision must be measured again after Wave 3;
this planning revision is not a qualified baseline.

## 1. Measurement claim and limits

Measure a pinned framework + external Worker + model + executor combination,
with separately reported process correctness, discipline, efficiency, and
application quality. A score alone does not establish that the framework
caused an improvement. Compare Worker profiles only with the same framework,
case, scoring revision, variant schedule, budgets, and host profile.
A causal framework-benefit claim additionally needs a matched ablation with
the same Worker and task; it is not a prerequisite for implementing J03.
Do not call a synthetic transcript, reference interpreter, or mock provider
an external Worker run.

The unit of evaluation is one clean run. A required campaign contains at
least three independently initialized runs with distinct session identities
and generated variants. Freeze the complete run schedule before execution.
Retries cannot replace a failed or invalid required run.

## 2. Repository and package boundaries

Keep the existing M01–M03 score contracts and J01 incubator intact. J03 needs
an explicitly selected versioned evaluator; never dispatch its Java suite
through the existing Python-only hidden-suite scorer.

Planned locations:

- process/bench/cases/J03-document-flow/: public intake, Worker instructions,
  baseline seed, public suite, and judge-only oracle/hidden_suite/mutations.
- scripts/document_flow/: judge orchestration, collectors, schemas, pure
  evaluator, variant generator, external adapter, and report renderer.
  These files are not imported by the installed Worker wheel.
- tests/bench/document_flow/: scoring, schema, isolation, collector,
  replay/recomputation, mutation, and CLI integration tests.
- backlog/product/v3/document-flow-benchmark/packages/01–07/: per-package
  RESULT.md and evidence indices.
- Operator-selected judge output root: bench/runs/<campaign>/<run>/;
  no qualification output is written into the Worker sandbox.

The installer uses an explicit public-file inventory, validates resolved
paths and rejects links/reparse points escaping the pack, and emits hashes
for all installed public files. It never copies the case directory wholesale.
Judge schemas describe benchmark reports, not DeltaFuse product artifacts.
Product behavior and event/API requirements reside only in the case/seed.

Proposed judge CLI: python -m scripts.document_flow with subcommands
preflight, init, run, replay, campaign, compare, and calibrate.
These are proposed interfaces, not commands that exist today.

## 3. Working seed and independent oracle

Use a Maven reactor with contract, document-service, workflow-service, and
audit-service modules, Java 21, Spring Boot, Kafka, PostgreSQL, and Flyway.
Pin direct and transitive dependency resolution and image digests in an
offline build inventory before qualification. Never invent registry digests.
Separate provisioning with allowed repositories from offline execution.

Each service owns a database and credentials with no cross-service write
privileges. document-service owns immutable versions and an outbox;
workflow-service owns routes, slots, inbox, and outbox; audit-service owns an
append-only projection and deduplication keys. Public baseline implements
single-step approval only. A target implementation is judge-only.

Resolve cross-service atomicity explicitly: superseding the old route and
creating its successor occurs in one workflow-service database transaction.
Document publication is asynchronous through its outbox. The public contract
must expose pending synchronization rather than promise a distributed ACID
transaction. This interpretation must be fixed in the public case before
Worker runs; if it differs from intended semantics, use a real Human Gate.

Define exact public JSON/event contracts, identity, error outcomes, ordering,
HTTP idempotency, and versioning before writing hidden tests. In particular,
freeze how actor-role authorization is supplied, whether registrar rejection
is valid, and how repeating a decision_id with a conflicting payload is
handled. Do not silently score unstated choices. Seed behavior must supply
an answer or the intake must explicitly describe the intended change.

The canonical read endpoint combines document, active version, route state,
open slots, and audit sequence. Use logical sequence keys, not wall-clock
arrival order, for canonical comparison. The endpoint may expose a readiness
marker for polling; a deadline is a bound, not evidence that convergence
actually happened.

Judge scenario generation is deterministic from a saved seed and generator
source hash. Generate UUIDs, role actors, document counts, delivery schedules,
duplicates, and restart points; record the exact generated operation stream.
Use explicit causal constraints so randomized delivery cannot accidentally
make a valid operation invalid. Invalid schedules are separately named cases.

Use an independent pure state interpreter to derive expected observable
results. Do not share transition code with Java seed/reference implementations.
The reference interpreter cannot prove inbox/outbox atomicity, restart safety,
or resource behavior: those checks execute against the actual container stack,
Kafka, and restricted read-only database assertions.

## 4. Deterministic stage oracles

Natural-language keyword hits cannot establish semantic correctness.
Require case-local structured obligation witnesses accompanying ordinary
DeltaFuse artifacts. Each witness maps an intake claim to a requirement,
typed predicate, exact spec anchor, task, public assertion, and result.
Publish the witness language and required observable semantics; keep expected
instances and test schedules private. Parse references and execute predicates.
Unknown predicates, vacuous conditions, contradiction, dangling links, and
unmapped obligations fail. This evaluates a bounded executable contract;
do not claim complete understanding of arbitrary prose.

| Stage | Correctness oracle | Primary evidence |
|---|---|---|
| Intake | Exact obligation coverage; unsupported claims; next step | Immutable intake, parsed claims, host file-access log, Core result |
| Analyze | Capability edges, cross-service/event/migration impact, complete bounded slices, correct ambiguity handling | Routing graph, slice witnesses, Core snapshots, Human Gate receipts |
| Specify | Typed invariants and API/event transition predicates, claim-to-spec coverage, unchanged baseline code | Spec witnesses, predicate interpreter, content inventories |
| Decompose | Requirement-to-task coverage, acyclic dependencies, prerequisites before effects, slice-local write sets | Task DAG, spec references, per-task packet measurements |
| Declare | Public assertions fail on baseline for the intended observable reason and kill corresponding mutants | Frozen test hashes, authenticated baseline command results |
| Implement | Frozen assertions preserved, Green/regression valid, task-local writes and hidden task behavior | Executor receipts, before/after trees, task checks |
| Verify | Complete traceability, terminal tasks, matching stack build, actual system checks, archive after convergence | Snapshot-bound system report and Core history |

Stage reports finalize from captured boundary snapshots, never from a later
finished tree. Repeated task Declare/Implement cycles remain individually
observable; aggregate them within the seven lifecycle report categories.
Do not assume there is exactly one linear invocation of each stage.
After early failure, finalized reports survive; later stages are explicitly
not reached and earn zero points, rather than guessed failure evidence.

Correctness totals 600 and discipline 250 per stage. Define a frozen
check inventory with explicit individual weights summing to those totals.
Boolean outcomes never supply their own weight. Missing checks earn zero.
Core gate success is corroborating evidence, not the semantic oracle.
A mandatory gate can prevent release even if its point weight is small.

## 5. Efficiency contract to freeze before reference runs

These definitions are design proposals pending tested scoring-contract freeze.

Each Worker call records measured input/output/framework tokens, tokenizer
fingerprint, file-read byte ranges and hashes, attempted writes, tool outcomes,
and compaction linkage. Source evidence remains judge-owned. A metric without
the required observations receives zero for its factor; missing mandatory
provenance may invalidate the run rather than merely reduce its score.

- context_efficiency: mean over observed calls of min(1, stage_call_budget /
  measured_context_tokens), with zero for overflow, unmeasured calls, or a
  stage with no calls. Stage budgets must be fixed by packet calibration and
  never exceed the hard context cap of 32768. Define context accounting to
  include retained thinking and reserved output before selecting the profile.
- file_focus: useful unique source files / all unique source files read into
  Worker-visible context, capped at one; zero without complete measured reads.
  Usefulness follows the frozen task/capability closure plus required skills
  and Core inputs. Record byte ranges and re-reads separately to detect dumps
  and repeated tool waste. See SCORING-PLAN.md for the exact proposed contract.
- tool_efficiency: productive tool actions / attempted tool actions; zero
  without complete action observations. Errors, no-ops and identical retries
  with unchanged inputs are not productive. Read-only verification of newly
  changed inputs is productive. Freeze action classification rules in tests.
- retry_efficiency: successful required operations / (required operations +
  excess attempts); zero without authenticated command observations. Each
  task has its own gate/evidence operation identity. Expected Red assertion
  failure is not a failed Declare operation; corrected resubmissions count
  as excess attempts. Diagnostic Core queries are not fabricated successes.

Efficiency = round(150 * (0.40*C + 0.25*F + 0.15*T + 0.20*R)).
Specify exact rational arithmetic and round-half-to-even for all round()
operations; reject NaN, infinity, bool-as-int, negative counts and overflow.
Freeze budget functions and all numeric ceilings in a versioned contract
before reference runs. No post-hoc tuning on Worker results.

## 6. Scoring, invalidity, and campaigns

System groups total 1800 functional, 600 resilience, 400 consistency/
compatibility, and 200 resource efficiency. Fixed scenario weights sum to
each group; no bonus for duplicate test IDs or repeated passing tests.

Recompute stage/system points from raw checks and authenticated observations.
raw = sum(seven stage scores) + system score.
Valid score = max(1, min(10000, raw, applicable ceilings)).
Record all applicable ceilings, not just the minimum:

- incomplete lifecycle: 4999;
- functional system failure: 6999;
- observed forgery, unauthorized write, model/agent substitution: 1999.

Infrastructure failure, oracle exposure, or unverifiable provenance produces
score null and invalid verdict. When an authenticated trace proves an attack,
apply its valid-failed cap; when trust in the trace itself is lost, invalidate.
Thus a recorded attempted journal edit can be scored as misconduct, whereas
an unexplained missing host event segment cannot support a numeric score.
Invalidity takes precedence over ceilings. Release-pass additionally requires
every absolute acceptance gate, completed lifecycle, and qualified host.

Run tables must distinguish not reached, failed, invalid, and passed.
A Worker-produced compilation error is a product-build failure; a missing
judge build tool is infrastructure-invalid. Dependency drift caused by the
Worker is a valid Worker failure when host evidence proves its origin.
Preserve logs on every exit.

A campaign requires all preregistered runs, at least three, with identical
profile hashes and distinct session/sandbox identities. Any missing/invalid
required run makes campaign score null. Valid failed runs remain included.
Use exact arithmetic for 0.50*median + 0.30*minimum + 0.20*mean.
Include all run scores, pass rate with the full required-run denominator,
population variance, first-failure counts, and per-stage comparisons.
Cross-profile comparisons require matching contracts/variants; differences
in hardware are disclosed and wall time is never a quality ranking input.

## 7. Report and event integrity

Use strict JSON Schema for stage/system/run/campaign reports, attestation,
variant manifest, and source events. Every object is closed; all required
fields are explicit. Validate with no remote schema resolution.

Canonical JSON: UTF-8, sorted keys, compact separators, no floats for points,
no nonfinite numbers. A report's hash excludes only its own hash field.
Content hashes alone do not authenticate origin: store host events in an
append-only judge-owned stream with sequence numbers, previous hashes,
content-addressed command artifacts, and an external sealed run manifest.
The Worker cannot access signing/sealing material or the output directory.

All evidence references resolve within the run's content-addressed artifact
store. Reject traversal, escaping links, missing objects, hash mismatches,
duplicate identities and report/profile/snapshot substitutions.
Reports are create-only and fsynced before atomic finalization. Recovery
records an interrupted run and retains earlier stages; it does not overwrite
an old run or invent the missing terminal event.

Replay ignores stored totals, reconstructs the score, and compares all derived
fields. Mutation tests must alter both a stored score and its self-hash;
semantic replay still rejects the forgery.
Report rendering produces JSON plus Markdown stage tables; comparison uses
the same evaluator, not separately maintained score arithmetic.

## 8. External Worker and execution boundary

Inspect the installed little-coder package/version and documented extension
interfaces before adapter implementation. Do not invent flags or substitute
the qualification runner's internal model loop. The adapter launches a fresh
external session and captures its actual tool/compaction/model provenance.
Unavailable hooks for mandatory observations are a preflight failure.

Pin little-coder package hash, extension allow-list, model/provider/weights/
quantization attestation, tokenizer fingerprint, configuration, and image.
One model performs all stages with thinking retained; dispatch, subagents,
browser, search/fetch tools, and unobserved execution paths are disabled.
A wrapper's declared config is insufficient: probe effective behavior.

Separate trust domains:

1. Judge controller: has pack, hidden code, artifacts, sealing keys.
2. Worker agent: public sandbox and pinned wheel only, inference egress via an
   allow-listed proxy; no judge/parent mounts or container runtime socket.
3. Worker commands/builds: isolated execution with public cached dependencies,
   no arbitrary internet and enforced Core write envelope.
4. Product system: three services, Kafka and PostgreSQL on a private network;
   no judge source mounted and no host/runtime privileges.
5. Judge clients: invoke public API/Kafka and scoped read-only SQL assertions.

Observe shell subprocess reads and writes as well as native agent tools.
A read_file/write_file interceptor alone is insufficient. Enforce the current
Core envelope over arbitrary shell commands; capture attempted denied writes.
Log stage snapshots outside the boundary. Probe the actual Worker/command
environment before and after execution, including parent traversal, mounts,
egress, tool escape, symlinks, and renamed sentinel exposure.

Human Gates halt the Worker. Record actual operator decisions; never silently
auto-accept specification or ambiguous Decisions. Time awaiting a Gate is
diagnostic, excluded from efficiency. An unattended halt stays incomplete.

## 9. System scenarios and mutation calibration

Implement every INSTRUCTION.md section 7.1 scenario. Use broker-aware barriers,
deadline polling of observed invariants, and explicit fault-injection points
around commit/ack and publish/sent. Prove a crash point was reached before
claiming restart coverage. Infrastructure faults must not count as mutant kills.

Calibrate all 24 listed mutants and extra evaluator attacks. The matrix maps
each mutant to expected check IDs and fixture/patch hashes. A kill means its
expected check fails on a successfully executed workload; unrelated compilation
or infrastructure errors do not count. Mark critical mutants before running.
Require all critical mutants killed and at least 90% overall.

Distinguish process-artifact mutations, real Java application mutations, and
report/measurement mutations. Altering a check's pass boolean is not an
application mutation. Run baseline negative control and positive Java reference
control before interpreting mutation detection. Independently perturb scenario
seeds to detect public-case hardcoding.

## 10. Seven implementation packages and exit criteria

| Package | Work | Required evidence |
|---|---|---|
| 01 scoring contracts | Closed schemas, rational pure evaluator, event integrity, replay and campaign rules | Red/Green, all boundary/invalidity/cap tests, malformed/missing data, score rehash forgery |
| 02 working seed | Three real services, migrations, baseline contracts, public tests, pinned offline Compose | Windows/POSIX Java 21 build, baseline public smoke, immutable versions, replay/dedup |
| 03 generated oracle | Versioned generator, independent interpreter, real hidden clients, private reference implementation | Baseline fails target checks; reference passes; randomized variants; repeatable expected output |
| 04 lifecycle reports | Core adapters, snapshot collector, witnesses, measured efficiency, Markdown renderer | All seven reports, multi-task cycles, genuine Gate pause/resume, early failure recovery |
| 05 external adapter | little-coder integration, effective profile and host attestation, envelope/egress enforcement | Live boundary attacks denied, complete call-level trace, no internal-loop substitution |
| 06 mutation matrix | 24+ executable mutants and expected detections | All critical kills and >=90%; no infra-error kills; baseline/reference controls |
| 07 qualification | Clean builds/runs, pilot, three-run campaign, replay, comparison and EN/RU guide | Full stack evidence, external pilot, schema/recomputation, smoke/layout/asset drift and legacy search |

For each package record full parent SHA and final commit identity (in a
subsequent evidence manifest to avoid a self-referential commit hash), exact
commands and exit codes, runtime versions, hashed evidence paths, limitations,
and Red/Green results in RESULT.md. Do not state the benchmark is ready until
all INSTRUCTION.md acceptance criteria have real evidence.

## 11. Immediate next action

Complete/verify QF-023–QF-025 externally to this benchmark change, then capture
a clean approved DeltaFuse 3.0.0 SHA and initialize an isolated benchmark branch.
Re-read current contracts at that revision. Begin package 01 with failing
tests; do not absorb the current dirty asset work into the benchmark baseline.
