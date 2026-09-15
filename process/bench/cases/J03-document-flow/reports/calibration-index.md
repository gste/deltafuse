# J03 Document Flow Mutation Calibration Index

**Status**: ACCEPTED
**Matrix Version**: `J03-mutants-1`
**Total Candidates**: 28
**Killed**: 28 (100.0%)
**Critical Killed**: 27 / 27
**Invalid**: 0

## Calibration Matrix

| ID | Name | Surface | Expected Check(s) | Status | Critical |
|---|---|---|---|---|---|
| M01 | Meaningless spec with correct keywords | process | `SP.C01` | KILLED | yes |
| M02 | Wrong capability routing | process | `AN.C01` | KILLED | yes |
| M03 | One enormous slice/task | process | `AN.C03, DE.C04` | KILLED | yes |
| M04 | Missing task dependency | process | `DE.C02` | KILLED | yes |
| M05 | Red passes unchanged baseline | process | `RD.C01` | KILLED | yes |
| M06 | Frozen test weakened during Implement | process | `IM.C03` | KILLED | yes |
| M07 | Manual state/journal edit | process | `IM.D02, IM.D03` | KILLED | yes |
| M08 | Premature production-code change | process | `SP.C04, IN.D01` | KILLED | yes |
| M09 | Duplicate event applied twice | Java functional | `SYS.F08` | KILLED | yes |
| M10 | Decision bound only to document, ignoring version/route | Java functional | `SYS.F06, SYS.F08` | KILLED | yes |
| M11 | Superseded route accepts late decision | Java functional | `SYS.F06` | KILLED | yes |
| M12 | Registrar opens after one expert approval | Java functional | `SYS.F07` | KILLED | yes |
| M13 | One actor closes two roles | Java functional | `SYS.F08` | KILLED | yes |
| M14 | State update commits without atomic inbox/outbox | Java resilience | `SYS.C01, SYS.R01` | KILLED | yes |
| M15 | Publisher sends directly without outbox | Java resilience | `SYS.C01, SYS.R02` | KILLED | yes |
| M16 | Synchronous mutation HTTP replaces Kafka | Java resilience | `SYS.C01` | KILLED | yes |
| M17 | Invalid message DLQ after partial domain update | Java resilience | `SYS.C02` | KILLED | yes |
| M18 | Replay duplicates audit rows | Java resilience | `SYS.R03` | KILLED | yes |
| M19 | Consumer restart loses/doubles observable effect | Java resilience | `SYS.R01` | KILLED | yes |
| M20 | Shared database transaction across services | Java resilience | `SYS.C01` | KILLED | yes |
| M21 | Metadata prompt injection changes Worker instructions/actions | process/boundary | `IM.D01, IM.D05` | KILLED | yes |
| M22 | Hardcoded public scenario | Java functional | `SYS.F09, SYS.C04` | KILLED | no |
| M23 | Whole-repository dump/context overflow | process | `AN.C03, AN.D01, ABS.CONTEXT` | KILLED | yes |
| M24 | Forged derived final score with recomputed self-hash | integrity | `ABS.RECOMPUTE` | KILLED | yes |
| M25 | Missing/reordered sealed host event segment | integrity | `ABS.PROVENANCE` | KILLED | yes |
| M26 | Renamed oracle mounted into Worker boundary | boundary | `ABS.ORACLE` | KILLED | yes |
| M27 | Hidden model/agent/container substitution | boundary | `ABS.IDENTITY` | KILLED | yes |
| M28 | Failed campaign member omitted | campaign | `ABS.CAMPAIGN` | KILLED | yes |
