# J03 interface and artifact blueprint

These are proposed package interfaces. No listed new module/CLI is implemented
by the planning task. Follow current DeltaFuse producer contracts when coding.
Never amend its Process to make a benchmark convenient.

## Trust domains and locations

Public case root: process/bench/cases/J03-document-flow/seed plus public_suite,
input.md and WORKER.md copied by an allow-listed inventory.
Private pack: oracle, hidden_suite, mutations, reports and scripts/document_flow.
Public runtime wheel must contain neither judge code nor private assets.
A path named public is not proof: validate complete manifests and image/wheel
contents. Install public tests under explicit approved product test paths.

Judge root is external to the Worker environment and implementation checkout.
Worker tools have no parent-repo traversal, host mount, Docker socket or
unrestricted network. The product stack has private broker/database networking.
The external agent can reach only an attested inference endpoint through a
controlled proxy. Judge observations flow out through host-owned channels.

## Proposed artifact layout

bench/runs/<campaign>/
  campaign-plan.json          # immutable schedule and profile/contract refs
  <run>/
    manifest.json             # identities, declared required stages, seal refs
    events/host.jsonl         # ordered host-owned event source
    objects/<sha256>          # content-addressed bytes: stdout, source, etc.
    snapshots/<visit>.json    # exact before/after tree + Core state inventories
    visits/<stage>/<visit>.json
    stages/01-intake.json ... 07-verify.json
    system.json
    run.json
    report.md
  campaign.json
  comparison.md

Run names are safe single identifiers. Reject traversal/absolute/alternate
stream paths, symlink/junction escape and output inside Worker sandbox.
Creation refuses occupied output; no destructive force reset for evidence.
Mutable in-progress storage is not a finalized report. On terminal/crash,
finalize available visits and rollups; later stages are not-reached.
A revisited stage adds a visit instead of editing prior evidence.
If early finalized stage report needs a new visit, emit a new immutable
revision with predecessor reference; the seven terminal aliases are finalized
only at run close. No overwrite of a prior report's content address.

## Public semantic witnesses

Ordinary DeltaFuse request/routing/slice/spec/task/evidence artifacts remain
mandatory. A case-local typed block provides a deterministic semantic witness
inside a path already allowed by the current stage envelope.
No blanket new framework schema requirement. J03-002 must prove placement.

Proposed witness has obligation_id, source_anchor, capability_id,
requirement_anchor, predicate={kind,args}, task_refs, assertion_refs.
Fields grow only at the appropriate lifecycle stage; earlier witnesses do
not pretend later evidence already exists. All IDs reference actual content
hashes/anchors. Predicate kinds have a finite public grammar: identity binding,
immutability, transition precondition/postcondition, idempotent observable
effect, role separation and atomic persistence relationship.

The public contract exposes syntax and semantics; private oracle supplies
expected predicates, scenario schedules and adversarial witnesses. Reject
unknown predicates, vacuity, contradictions, invented source claims and
dangling anchors. Do not use fuzzy string/keyword agreement as semantic proof.
This bounds what deterministic evaluation can know about prose; an additional
contradictory free-text requirement cannot be declared fully understood by a
non-LLM parser. Record that limit and require normative executable blocks for
the aspects being scored. Do not award a semantic pass just for valid syntax.

## Python module interfaces to establish

| Owner | Proposed API | Invariant |
|---|---|---|
| registry.py | load_registry(path) -> FrozenRegistry | IDs/weights/gates fixed and validated |
| validation.py | decode_validate(kind, bytes) -> typed mapping | closed schemas; duplicate keys/nonfinite rejected |
| canonical.py | canonical_bytes(value); content_hash(value) | deterministic encoding and self-hash policy |
| store.py | put(bytes)->Ref; resolve(Ref)->bytes; append(Event); finalize(Report) | judge-owned CAS and create-only finalization |
| variants.py | generate(seed, contract)->Variant | no external state; deterministic operation schedule |
| oracle/interpreter.py | reduce(operations)->ExpectedState | independent pure domain semantics |
| core_bridge.py | observe(product, executor)->CoreObservation | pinned real next/halt/envelope, not invented state |
| snapshots.py | capture(visit, observation)->SnapshotRef | immutable snapshot/event-range binding |
| oracles/<stage>.py | evaluate(snapshot, events, contract)->CheckFacts | named evidence-backed predicates, no self-reported points |
| efficiency.py | measure(stage_events, frozen_budget)->Factors | complete measured numerators/denominators |
| evaluate.py | evaluate_run(CheckFacts, Factors, identities)->RunSummary | exact totals/caps; no stored score input |
| replay.py | replay(run_dir, trusted_manifest)->RunSummary | resolves source objects and re-executes predicates |
| campaign.py | evaluate_campaign(plan, re_evaluated_runs)->CampaignSummary | all preregistered members retained |
| clients.py | HTTP/Kafka/read-only SQL observations | public surfaces and restricted database assertions only |
| system_runner.py | execute(snapshot, variant, profile)->SystemEvidence | actual built services, version/fault receipts |
| worker/adapter.py | start(profile,sandbox); stream(); pause(); close() | genuine external loop, explicit session identity |
| worker/command_boundary.py | execute(argv,envelope)->CommandReceipt | effective descendant restrictions + measured I/O |
| attest.py | attest(actual_runtime,profile)->Attestation | measured identity, not caller declarations |
| reports.py | render(recomputed_reports)->Markdown | presentation never owns score arithmetic |

CheckFacts are produced by judge predicates over authenticated raw inputs.
They are not accepted from Worker-written scorecards. Replay recalculates
facts, not merely sums saved pass flags. Integrate existing qualification
utilities only through stable tested helpers; do not import internal model
loop into the external adapter or copy the old score contract.

## Common JSON shapes

All objects closed with additionalProperties:false, every nested object
included. Schema version and local $id are explicit; no network $ref loading.

Identity: case/campaign/run/variant/stage/visit/task; framework commit/wheel/
lock; registry/generator/public/hidden pack hashes; agent/version/dependency/
config/extension hashes; model/provider/weights/quantization/tokenizer refs;
host/build/executor/container identities. References may group immutable
attestation fields but must resolve to complete required fields in stage export.

EvidenceRef: relative CAS key, SHA256, media type, byte length, producer/event
identity. A source outside the authorized evidence root is invalid.
Event common: schema_version, sequence, previous_hash, event_hash, monotonic
order, diagnostic timestamp, run/session/call/visit identity, event kind,
typed payload and host source. Secret headers are excluded/redacted before
persistence; redaction does not erase response model/token measurement.

Model call payload: actual input/output/framework tokens, reservation,
tokenizer/template fingerprint, usage source, request/response hashes,
thinking retention, active profile identity. Null=unmeasured; 0 is a real count.
File payload: canonical path, file hash, range, operation/read origin,
repeat relation, allowed/rejected state, tool/call/process identity.
Command payload: argv array (not unescaped shell string), cwd relative root,
environment inventory hash, start/finish, timeout, exit, stdout/stderr refs,
process/executor identity, target snapshot and operation instance.
Compaction payload: before/after session/request refs, cause, measured sizes,
retained/lost state checks. Gate payload: actual Core halt, chosen option,
operator identity/receipt, resume state; never fake an operator click.

Check result: registry ID, status, evaluated evidence refs, failure reason;
points are derived display output only. Stage report also includes lifecycle
start/end, all visits, calls/Core commands, files/re-reads, tool errors/timeouts/
denials, retries, compactions, wall time, next stage, factors, score and hard
failures. System report has per-scenario observations, build/fault/load IDs and
group totals. Run/campaign reports expose raw points, every ceiling,
validity/release verdict, source reports and diagnostics.

## Proposed CLI and exits

python -m scripts.document_flow preflight --plan PLAN --out NEW_DIR
python -m scripts.document_flow init --plan PLAN --run-id ID --sandbox NEW_DIR
python -m scripts.document_flow run --plan PLAN --run-id ID --out NEW_DIR
python -m scripts.document_flow replay --run RUN_DIR --trusted-manifest MANIFEST
python -m scripts.document_flow campaign --plan PLAN --runs ROOT --out NEW_DIR
python -m scripts.document_flow compare --left CAMPAIGN --right CAMPAIGN --out NEW_DIR
python -m scripts.document_flow calibrate --plan MATRIX --out NEW_DIR

CLI names/flags must get parser tests in J03-507; they are not current commands.
Plan files supply explicit pack/profile/variant/build IDs; CLI cannot silently
take today's global defaults. run never resumes/replaces an existing scored
run; real Gate continuation must preserve authenticated session identity.

Proposed exit contract: 0 completed requested validation/execution successfully;
1 valid failed run/calibration; 2 invocation or unmet preflight prerequisite;
3 invalid infrastructure/host/provenance/oracle outcome; 4 awaiting real Human
Gate; 130 cancellation. Details retained in typed report regardless of exit.
For replay, 0 means recomputation matches, not that the stored run passed.
Scripts consume verdict fields instead of treating every exit=0 as release-pass.

## Calibration and build-control knobs

Choose exact dependency/container versions and resolve digests during approved
provisioning. Commit hashes/inventory, never ephemeral credentials.
Java 21 and reproducible Maven plugin/transitive dependency closure required.
Baseline verification includes actual service unit, database/broker integration
and public system smoke. Maven profiles in cards are planned additions.

Fault control must acknowledge the measured barrier before killing a process.
Test-only hooks expose no judge logic or answer fixtures. Use public build
instrumentation and out-of-process tracing when Worker-authored hooks cannot
be trusted; fault receipts must prove the asserted transaction location.

Resource budgets are calibrated on fixed host and frozen before Worker runs.
Observe SQL counts independently (e.g. pinned database instrumentation),
offset/replay work, memory/restarts and exact final state. Do not rely solely
on application self-reported counters. Avoid host-global Docker cleanup;
only run-labelled containers/networks/volumes may be removed after evidence
has been preserved and resolved ownership checked.
