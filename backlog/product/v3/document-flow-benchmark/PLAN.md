# J03 comprehensive implementation plan

Status: **ready for implementation handoff; no implementation executed**.
Source: [INSTRUCTION.md](INSTRUCTION.md). Architecture: [DESIGN.md](DESIGN.md).
Execution: [EXECUTOR.md](EXECUTOR.md). Machine queue: [queue.json](queue.json).

## Outcome and critical path

Deliver a working three-service Java 21 baseline, independent generated judge,
seven-stage deterministic scoring, an attested external little-coder/Laguna
adapter, 28-mutant calibration, replayable run/campaign evidence and usage docs.
Use DeltaFuse 3.0.0 as the subject. Preserve M01–M03 and J01 unchanged.

The plan has **58 bounded cards** in eight groups: prerequisite group 00 and
the seven implementation packages mandated by INSTRUCTION.md.
The dependency graph is acyclic. Numeric order is a valid default execution
order; dependency completion still determines readiness.

Critical path:
qualified clean baseline -> public semantics/host/Worker feasibility ->
scoring contracts -> green seed -> independent oracle/reference/system suite ->
stage collectors/replay -> external adapter/boundary -> mutation calibration ->
clean qualification -> actual pilot -> three-run campaign -> acceptance close.

Independent branches within a package are encoded in queue.json for scheduling,
not permission to launch additional agents. Default execution is one card at a
time. Package 03 never earns release credit from the reference interpreter
alone; package 05 never substitutes the existing internal qualification loop.

## Package boundaries

| Group | Cards | Exit gate |
|---|---:|---|
| 00 entry | 4 | QF-025 verified, clean 3.0.0 pin, observable external profile and explicit public semantics |
| 01 contracts | 8 | Closed schemas, exact evaluator, ceilings, integrity and campaign boundary tests |
| 02 seed | 10 | Real single-step baseline stack green; public inventory excludes all private assets |
| 03 oracle | 8 | Private reference passes and unchanged seed fails target IDs; real fault/resource observations |
| 04 stages | 9 | Seven stage reports from immutable visits, authentic evidence, disk re-evaluation and readable output |
| 05 adapter | 8 | Actual external process transport and effective measured isolation; mock probe is explicitly non-release |
| 06 calibration | 5 | All critical mutants killed, >=90% overall, no infra-error kills; judge contract frozen |
| 07 qualification | 6 | Both platforms, full stack, external pilot, three independent runs, all 15 acceptance criteria reconciled |

## Queue

All statuses below are planned. Update queue.json and the matching card/results
together during future implementation. First card: **J03-000**.

| Card | Group | Task | Dependencies |
|---|---|---|---|
| [J03-000](cards/J03-000.md) | 00 | Capture qualified framework baseline | entry |
| [J03-001](cards/J03-001.md) | 00 | Prove external Worker instrumentation feasibility | J03-000 |
| [J03-002](cards/J03-002.md) | 00 | Freeze public semantics and judge observability | J03-000 |
| [J03-003](cards/J03-003.md) | 00 | Define reproducible host and dependency provisioning | J03-000 |
| [J03-101](cards/J03-101.md) | 01 | Create frozen check registry | J03-001, J03-002, J03-003 |
| [J03-102](cards/J03-102.md) | 01 | Define raw event schemas and safe decoding | J03-101 |
| [J03-103](cards/J03-103.md) | 01 | Define stage and system report schemas | J03-102 |
| [J03-104](cards/J03-104.md) | 01 | Define run and campaign schemas | J03-103 |
| [J03-105](cards/J03-105.md) | 01 | Define attestation and variant schemas | J03-102 |
| [J03-106](cards/J03-106.md) | 01 | Implement pure run scoring and failure precedence | J03-103, J03-104, J03-105 |
| [J03-107](cards/J03-107.md) | 01 | Implement campaign and comparison arithmetic | J03-106 |
| [J03-108](cards/J03-108.md) | 01 | Implement evidence store and sealed event integrity | J03-102, J03-106 |
| [J03-201](cards/J03-201.md) | 02 | Pin Java reactor and offline dependency inventory | J03-003, J03-107, J03-108 |
| [J03-202](cards/J03-202.md) | 02 | Publish baseline event/API contracts | J03-201, J03-002 |
| [J03-203](cards/J03-203.md) | 02 | Create isolated service schemas and migrations | J03-202 |
| [J03-204](cards/J03-204.md) | 02 | Implement document baseline commands | J03-203 |
| [J03-205](cards/J03-205.md) | 02 | Implement single-step workflow baseline | J03-203 |
| [J03-206](cards/J03-206.md) | 02 | Implement reliable Kafka inbox/outbox delivery | J03-204, J03-205 |
| [J03-207](cards/J03-207.md) | 02 | Implement audit projection and canonical query | J03-206 |
| [J03-208](cards/J03-208.md) | 02 | Wire pinned Compose stack and fault controls | J03-207 |
| [J03-209](cards/J03-209.md) | 02 | Prove public baseline end to end | J03-208 |
| [J03-210](cards/J03-210.md) | 02 | Add realistic noise and safe public pack installation | J03-209 |
| [J03-301](cards/J03-301.md) | 03 | Generate replayable scenario variants | J03-210, J03-105 |
| [J03-302](cards/J03-302.md) | 03 | Build independent pure domain interpreter | J03-301 |
| [J03-303](cards/J03-303.md) | 03 | Create private reference version-supersede implementation | J03-302 |
| [J03-304](cards/J03-304.md) | 03 | Complete private reference parallel approval implementation | J03-303 |
| [J03-305](cards/J03-305.md) | 03 | Build judge clients and stack execution harness | J03-304, J03-108 |
| [J03-306](cards/J03-306.md) | 03 | Implement hidden functional scenarios | J03-305 |
| [J03-307](cards/J03-307.md) | 03 | Implement hidden transaction and resilience scenarios | J03-305 |
| [J03-308](cards/J03-308.md) | 03 | Implement hidden bounded load and resource checks | J03-306, J03-307 |
| [J03-401](cards/J03-401.md) | 04 | Adapt Core snapshots without changing the Process | J03-308 |
| [J03-402](cards/J03-402.md) | 04 | Capture immutable stage and task boundary snapshots | J03-401 |
| [J03-403](cards/J03-403.md) | 04 | Implement Intake and Analyze deterministic oracles | J03-402, J03-101 |
| [J03-404](cards/J03-404.md) | 04 | Implement Specify and Decompose deterministic oracles | J03-403, J03-302 |
| [J03-405](cards/J03-405.md) | 04 | Implement authentic Declare and frozen test oracle | J03-404, J03-305 |
| [J03-406](cards/J03-406.md) | 04 | Implement Implement and Verify convergence oracles | J03-405, J03-308 |
| [J03-407](cards/J03-407.md) | 04 | Compute measured context/file/tool/retry efficiency | J03-402, J03-106 |
| [J03-408](cards/J03-408.md) | 04 | Re-evaluate runs from source artifacts | J03-406, J03-407, J03-108 |
| [J03-409](cards/J03-409.md) | 04 | Render reports and define read-only report commands | J03-408, J03-107 |
| [J03-501](cards/J03-501.md) | 05 | Integrate external little-coder session transport | J03-001, J03-409 |
| [J03-502](cards/J03-502.md) | 05 | Capture actual model and compaction measurements | J03-501, J03-407 |
| [J03-503](cards/J03-503.md) | 05 | Enforce native tool envelopes and disabled capabilities | J03-501, J03-401 |
| [J03-504](cards/J03-504.md) | 05 | Observe and confine arbitrary shell subprocesses | J03-503, J03-502 |
| [J03-505](cards/J03-505.md) | 05 | Enforce isolated Worker network and filesystem policy | J03-504, J03-208 |
| [J03-506](cards/J03-506.md) | 05 | Seal actual host/agent/model attestation | J03-505, J03-105 |
| [J03-507](cards/J03-507.md) | 05 | Wire runner CLI and durable failure handling | J03-506, J03-409, J03-305 |
| [J03-508](cards/J03-508.md) | 05 | Verify adapter with real process and no scored Worker campaign | J03-507 |
| [J03-601](cards/J03-601.md) | 06 | Implement process-artifact mutants | J03-508 |
| [J03-602](cards/J03-602.md) | 06 | Implement Java functional mutants | J03-601 |
| [J03-603](cards/J03-603.md) | 06 | Implement Java delivery and atomicity mutants | J03-602 |
| [J03-604](cards/J03-604.md) | 06 | Implement score/provenance and boundary mutants | J03-603 |
| [J03-605](cards/J03-605.md) | 06 | Run complete calibration and freeze judge pack | J03-604 |
| [J03-701](cards/J03-701.md) | 07 | Capture clean qualification build and public/judge inventories | J03-605 |
| [J03-702](cards/J03-702.md) | 07 | Qualify Windows baseline, framework and system harness | J03-701 |
| [J03-703](cards/J03-703.md) | 07 | Qualify POSIX baseline, framework and recovery | J03-702 |
| [J03-704](cards/J03-704.md) | 07 | Run fully attested external Worker pilot | J03-703 |
| [J03-705](cards/J03-705.md) | 07 | Execute three-run campaign and independent replay | J03-704 |
| [J03-706](cards/J03-706.md) | 07 | Close acceptance matrix and publish benchmark usage docs | J03-705 |

## Contract ownership and change control

[CONTRACTS.md](CONTRACTS.md) owns proposed interfaces/data shapes.
[SCORING-PLAN.md](SCORING-PLAN.md) owns candidate weights/factors/precedence.
[DECISIONS.md](DECISIONS.md) separates explicit intent from public case choices.
[MUTATION-PLAN.md](MUTATION-PLAN.md) owns the frozen candidate/check mapping.
These are planning contracts. Package 00/01 turns them into reviewed versioned
executable contracts before reference runs; results must never retune them.
An unresolved requirement affecting outcomes blocks dependent work only.

When splitting or revising cards, rerun dependency, weight, link and acceptance
coverage validation. Preserve stable IDs and completion evidence; supersede
rather than erase historical results.

## Risk-first schedule

J03-001 deliberately checks little-coder observability early. J03-002 resolves
distributed semantics and witness/envelope compatibility before hidden tests.
J03-003 plans offline dependency provisioning before Java builds.
Container file telemetry and shell write enforcement are substantial engineering
work, isolated in J03-504; if infeasible, record a release blocker instead of
lowering the measurement contract. Financial/provider/host availability is
preflight evidence, not a presumed future capability.

## Explicit limits of this planning delivery

All code paths under scripts/document_flow and new J03 case/tests referenced
by cards are future outputs. Example CLI names and profiles are proposed
interfaces; do not claim those commands currently exist.
The Docker daemon was verified reachable; no image was pulled or stack started.
No benchmark implementation, mutation run, Worker pilot or campaign occurred.
