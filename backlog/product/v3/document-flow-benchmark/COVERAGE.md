# Acceptance and requirement coverage

This is a planning coverage matrix, not passing evidence.
Each row must acquire immutable evidence references in package 07.

## Fifteen mandatory acceptance criteria (INSTRUCTION section 14)

| # | Acceptance | Implementing/verifying cards | Required evidence |
|---|---|---|---|
| 1 | Seed builds/public baseline on Windows and POSIX | J03-201–209, J03-702, J03-703 | Java 21 offline build, public unit/integration/system logs on both platforms |
| 2 | Clean Compose stack without manual steps | J03-208, J03-209, J03-701–703 | Pinned identities, clean-volume launch, health/API observations |
| 3 | Unchanged seed fails target oracle | J03-303–308, J03-605 | Expected named target failures, not infrastructure errors |
| 4 | Private reference passes all checks | J03-303–308, J03-403–408, J03-605 | Actual Java target stack plus valid process/reference artifacts |
| 5 | Repeated judge evaluation identical scores | J03-108, J03-408, J03-605, J03-705 | Two source-based replays, matching semantic hash/totals |
| 6 | Schemas and semantic recomputation fail closed | J03-101–108, J03-408, J03-604 | Malformed/forged/missing-evidence negative tests |
| 7 | 24+ mutants and detection matrix | J03-601–605 | All 28 results, critical kills and >=90%, no infra-error kills |
| 8 | Stage reports survive later failure | J03-402, J03-409, J03-507 | Early crash/stop with immutable earlier reports |
| 9 | 1..10000 formula/ceilings boundary tested | J03-106, J03-107 | Exact arithmetic, all cap/invalidity boundary cases |
| 10 | Campaign recomputed from three directories | J03-107, J03-408, J03-705 | Complete schedule, three independent source-evidence runs |
| 11 | Hidden pack inaccessible to Worker/mounts | J03-210, J03-503–506, J03-701 | Inventory/wheel/image tests and effective live boundary probes |
| 12 | Per-call context/files/retries measured | J03-001, J03-407, J03-502–504, J03-704 | Actual outbound request/tokenizer/file/tool/command/compaction receipts |
| 13 | little-coder/Laguna pilot with provenance | J03-501–508, J03-704 | Actual external process/model run, not scripted substitute |
| 14 | Framework smoke/layout/assets/legacy checks | J03-701–703, J03-706 | PS/POSIX smoke/layout, pytest, asset drift and classified legacy hits |
| 15 | Clean trees before/after qualification | J03-000, J03-701–706 | Full SHA/status records; evidence outside tracked source |

## Instruction sections

| Section | Coverage |
|---|---|
| 1 goals/measurement | DESIGN, SCORING-PLAN, J03-106/107/407/705; causal benefit claim limited without ablation |
| 2 start/boundaries | J03-000, J03-210, EXECUTOR; preserved M01–M03/J01 |
| 3 seed | J03-201–210; actual Java services, noise, pinned offline stack |
| 4 target behavior | J03-002/202/210/301–308; public intake/private target reference |
| 5 pack/variants/isolation | J03-105/210/301/503–506 |
| 6 stages/measurement | J03-101–108/401–409/502–504 |
| 7 system/efficiency | J03-305–308; SYS.F/R/C/E registry |
| 8 score/caps | J03-106, SCORING-PLAN and integrity mutants |
| 9 campaigns | J03-107/705; no dropping invalid/failed runs |
| 10 schemas/reports/recompute | J03-102–108/408/409 |
| 11 actual external Worker | J03-001/501–508/704 |
| 12 mutation calibration | All 28 matrix entries, J03-601–605 |
| 13 failure classes/artifact preservation | J03-104/106/108/305/402/507 |
| 14 acceptance | Fifteen-row matrix above, J03-706 closes |
| 15 seven packages/results | PLAN, EXECUTOR, RESULT-TEMPLATE, all cards |
| 16 deliverables | J03-210 active case; 301–308 judge; 501–508 adapter; 102–108/409 reports; 605/701–706 evidence/docs |

## Actual system scenarios

Normal staged approval F01; each expert reject F02/F03; duplicate HTTP/decision/
delivery F08/R01; supersede before/after partial approval F04/F05; late
approve/reject F06; early registrar F07; interleaved documents F09; consumer
restart R01; publisher restart R02; replay R03; DB/Kafka outage R04;
invalid schema/DLQ C02; metadata prompt injection C02 plus IM.D01/D05 and M21;
baseline compatibility C03; bounded load state C04 and resources E01–E04.

## Completion evidence rule

A link to a task or test file is not acceptance evidence. Each final row needs:
tested implementation SHA; exact command and exit; host/runtime profile;
artifact hash; named positive/negative check outcomes; measured versus mocked
classification; relevant run/snapshot identity. Missing evidence keeps the
criterion open. Do not mark the benchmark ready on runner unit tests alone.
