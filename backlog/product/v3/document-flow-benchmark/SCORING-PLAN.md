# Candidate scoring contract for package 01

Planning revision: J03-plan-1. This is a concrete proposed registry to implement
and freeze **before reference runs**, not a measured result.
INSTRUCTION.md owns the stage/system weights, 1..10000 scale, ceilings and
campaign formula. Internal check allocations below are design choices.
They cannot silently change after reference/Worker results are observed.

## Registry

All scored checks are binary with explicit prerequisites and evidence sources.
A check cannot bring its own points or change another check's weight.
Unknown/duplicate IDs or malformed primitive observations are invalid evidence.
A legitimate failed check earns zero; not-reached earns zero and is displayed
separately. Mandatory missing source provenance invalidates the run.
Every correctness and discipline check is mandatory for release-pass; points
remain useful for diagnosing valid failed runs. Efficiency factors need not
equal one for release, but context cap and telemetry completeness are hard gates.

Each stage receives exactly 600 correctness points:

| Stage | Check | Points | Required predicate |
|---|---|---:|---|
| intake | IN.C01 | 240 | All intended obligations covered |
| intake | IN.C02 | 180 | No invented or contradictory claims |
| intake | IN.C03 | 120 | Immutable intake and exact provenance links |
| intake | IN.C04 | 60 | Correct normalized artifact and next Analyze selection |
| analyze | AN.C01 | 180 | Exact capability routing |
| analyze | AN.C02 | 180 | Three-service/event/migration impact closure |
| analyze | AN.C03 | 140 | Bounded complete slices |
| analyze | AN.C04 | 100 | Correct real ambiguity and Decision handling |
| specify | SP.C01 | 240 | Executable version/workflow/delivery semantics |
| specify | SP.C02 | 160 | Exact API/event/state contracts |
| specify | SP.C03 | 120 | Complete claim-to-spec witnesses |
| specify | SP.C04 | 80 | Production baseline unchanged |
| decompose | DE.C01 | 200 | Complete requirement-to-task coverage |
| decompose | DE.C02 | 160 | Correct acyclic prerequisite edges |
| decompose | DE.C03 | 140 | Task write sets fit slices |
| decompose | DE.C04 | 100 | Task packet fits frozen bounded context |
| declare | RD.C01 | 220 | Authentic expected observable Red on unchanged baseline |
| declare | RD.C02 | 160 | Public requirement targeting and no private-only assertion |
| declare | RD.C03 | 120 | Mutation-sensitive frozen assertions |
| declare | RD.C04 | 100 | Complete requirement/test/evidence binding |
| implement | IM.C01 | 240 | Task observable correctness |
| implement | IM.C02 | 160 | Authentic Green and regression |
| implement | IM.C03 | 120 | Frozen Red and allowed production scope preserved |
| implement | IM.C04 | 80 | Build/dependency identity and compatibility |
| verify | VE.C01 | 180 | Complete raw-claim-to-result coverage |
| verify | VE.C02 | 180 | Snapshot-bound actual system result |
| verify | VE.C03 | 140 | Terminal tasks and cross-artifact convergence |
| verify | VE.C04 | 100 | Archive only after authentic convergence |

Apply the following five checks separately at each stage prefix, for 250 points:

| Suffix | Points | Required predicate |
|---|---:|---|
| D01 | 80 | Observed read/write envelope and source boundaries |
| D02 | 60 | Legal Core order, task lifecycle and Human Gates |
| D03 | 50 | Authentic complete host/Core/command receipts |
| D04 | 40 | Source/snapshot/spec/task/evidence identity linkage |
| D05 | 20 | No forbidden tool/model/agent privilege substitution |

The same violation may affect its correctness predicate and discipline points
if their published meanings differ; record the shared evidence link. No
unpublished penalty or duplicated point row is permitted.

System groups total 3000:

| Check | Points | Scenario |
|---|---:|---|
| SYS.F01 | 300 | Normal legal+security then registrar approval |
| SYS.F02 | 150 | Legal expert reject |
| SYS.F03 | 150 | Security expert reject |
| SYS.F04 | 250 | Supersede before expert approval |
| SYS.F05 | 250 | Supersede after one expert approval |
| SYS.F06 | 150 | Late approve/reject of superseded route |
| SYS.F07 | 150 | Early registrar invalid without transition |
| SYS.F08 | 200 | Command/decision identity, duplicates and distinct role actors |
| SYS.F09 | 200 | Independent interleaved documents |
| SYS.R01 | 180 | Consumer restart between commit and acknowledgement |
| SYS.R02 | 160 | Publisher restart between publish and sent marking |
| SYS.R03 | 160 | Full topic replay and audit deduplication |
| SYS.R04 | 100 | Temporary PostgreSQL/Kafka outage and recovery |
| SYS.C01 | 160 | Inbox/state/outbox atomicity; service database separation; Kafka delivery |
| SYS.C02 | 80 | Invalid schema/version DLQ without domain mutation; metadata remains data |
| SYS.C03 | 80 | Single-step baseline backward compatibility |
| SYS.C04 | 80 | Bounded load final state/event consistency |
| SYS.E01 | 70 | Bounded SQL statements per command/event |
| SYS.E02 | 50 | No unbounded topic replay on ordinary request |
| SYS.E03 | 40 | Bounded completion in frozen host environment |
| SYS.E04 | 40 | Heap/container limits with no OOM/restart loop |

F=1800; R=600; C=400; E=200.
Within a check covering several subcases (e.g. both late approve and reject),
all preregistered subcases must pass for that check's fixed points. Report
individual subcase outcomes. Adding variants never multiplies available points.
Each required fault scenario needs positive evidence its fault was triggered.
A timeout without observations of correctness cannot yield a pass.

## Efficiency, 0..150 per stage

Factors are exact rational values in [0,1]; never use binary float for scoring.
round() means nearest integer, ties to even, for both stage and campaign.
Reject bool-as-int, negative counts, nonfinite values, overflow and contradictory
count totals. A missing factor receives zero, not a default of one. Missing
mandatory telemetry needed for trust additionally invalidates the run.

**Context C.** For each call measure actual sent input including retained
thinking and separately measure generated output. Enforce
input_context + reserved_output <= 32768 before dispatch and
input_context + actual_output <= 32768 after response. Do not count retained
thinking twice if already present in input. Provider-invisible/unmeasured
reasoning cannot be asserted measured. Record exact tokenizer/template basis.
Candidate per-call efficiency is min(1, frozen_stage_budget / measured_occupancy).
Zero for overflow, nonpositive/missing measurement or stage with no calls.
C is the mean over all actual calls in all visits to that stage.
Frozen_stage_budget and output reservation come from package 00 calibration;
no numerical value is invented in this plan beyond the mandated 32768 cap.
Hard overflow is also an absolute process failure even if other points remain.

**File focus F.** Use useful unique source files / all unique source files
read into Worker-visible context, consistent with INSTRUCTION.md.
Usefulness comes from the frozen capability/task closure plus named mandatory
skills/Core metadata. Freeze content identity handling (same path/new hash)
and mark ranges/re-reads separately. Directory listing and subprocess stdout
that expose source must be accounted for. A diagnosed repository dump sets
the factor to zero and records the context/envelope violation; define the dump
detector from actual context/read-volume evidence before calibration.
Normal compiler/library reads are command I/O diagnostics, not an artificial
inflation of model-visible useful files. Missing read telemetry is not zero
reads. Zero denominator or incomplete measurement gives F=0.

**Tools T.** Productive actions / attempted actions across all visits.
Productive means required read of new content, authorized effective edit or
valid verification of changed inputs. Error, denied, timeout, unchanged no-op
and identical retry with unchanged inputs are unproductive. Expected assertion
failure in a valid Declare run is productive. Freeze classification as a
versioned decision table with positive and negative fixtures.
Do not infer productivity from exit=0 alone. No measured actions gives T=0.

**Retries R.** Successful required operation instances /
(required operation instances + excess attempts).
An instance is (stage visit/task, operation kind, target evidence/spec hash).
Repeated gates after success, invalid submissions and retries without changed
prerequisites count as excess. Missing required operations remain in the
denominator. Expected Red is not itself an unsuccessful operation.
Diagnostic read-only Core queries are tracked as tools but cannot manufacture
successful required instances. No complete operation journal gives R=0.

efficiency = round(150 * (0.40*C + 0.25*F + 0.15*T + 0.20*R)).
Aggregate stage check predicates over all required tasks/visits; do not earn
600/250 anew per task. All required instances of a predicate must pass.
C/F/T/R are computed from combined underlying observations, not a rounded
average of already rounded per-task efficiency scores.

## Failure precedence

1. Validate structural schemas and identities, seal/source completeness,
   host/inference provenance and oracle isolation. Loss of trust or
   infrastructure failure -> score=null, verdict=invalid.
2. If trustworthy events establish a Worker failure, keep it valid-failed
   and evaluate earned points and all applicable ceilings.
3. Compute raw=sum(stage correctness+discipline+efficiency)+system groups.
4. For valid runs clamp to [1,10000], then apply all applicable ceilings:
   incomplete lifecycle 4999; functional system failure 6999;
   evidence forgery/unauthorized write/hidden identity substitution 1999.
   Record all ceilings; minimum wins. A failed build implies functional
   system failure. Unreached system checks earn no points.
5. Release-pass requires all absolute gates, real completed lifecycle, all
   mandatory scenario predicates and qualified provenance, regardless of sum.

An attempted denied unauthorized write is observed misconduct if policy
classifies it so; record attempted versus actual effect. Proven forgery inside
the Worker sandbox is a valid failure when host truth survives. Missing or
forged judge source evidence invalidates. Proven model substitution with an
intact trace gets the 1999 cap; unidentifiable provider response invalidates.

Taxonomy includes all ten INSTRUCTION.md section 13 classes plus a distinct
provenance-invalid reason under invalidity. Judge/client setup problems and
a Worker-authored product build error must never be conflated.

## Boundary fixtures

| Inputs | Expected |
|---|---|
| Valid raw=0, intact provenance, completed failed execution | score=1, fail |
| Valid raw=10000, all absolute gates pass | score=10000, release-pass |
| Raw=8000, lifecycle incomplete | 4999 cap |
| Raw=8000, system functional failure | 6999 cap |
| Raw=8000, proven forbidden write | 1999 cap, fail |
| Raw=8000, all three caps | 1999; all caps listed |
| Raw=100, all three caps | 100; all caps listed |
| Raw=10000, oracle leak | null, invalid |
| Raw=10000, missing host segment or unknown provider | null, invalid |
| Unreached stage | 0 stage points, not-reached label |
| Missing measured efficiency factor | factor=0; invalid if mandatory provenance lost |
| Saved score and its hash changed together | replay rejects derived mismatch |
| Registry weight changed after campaign freeze | identity mismatch, invalid |
| Invalid run with score=1 or 0 | schema/semantic rejection |

Include integer boundaries around every cap; all factor corners; rounding
ties; duplicate check/operation identities; cross-run artifact substitution;
missing evidence; contradictory metadata; failure-order determinism.

## Campaign

At least three preregistered independent session/sandbox identities on the same
frozen profile. Seeds/schedules fixed before runs. Compare against the required
run list, not a glob of successful report files.
Any missing/invalid required member -> campaign_score=null. Valid failures stay.
round(0.50*median + 0.30*min + 0.20*mean), exact rational arithmetic.
For scores [1,5000,10000], expected 3500; for [1,1,1], expected 1;
for [10000,10000,10000], expected 10000. Test even-sized median as well.
Pass rate uses all required runs as denominator; report population variance,
all scores, first-failure distribution and stage deltas, even if total is null.

Two re-evaluations of one sealed run must yield identical semantic results.
A fresh execution has different runtime diagnostics and is not expected to
produce byte-identical wall times. Separate semantic-result hash from full
report hash so this distinction is explicit.
