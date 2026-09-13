# Frozen candidate mutation matrix

Minimum source requirement: 24 known mutants, all critical detected, >=90%
overall, failures at expected check IDs. This plan supplies **28 candidates**.
Candidate critical flags are fixed before calibration; do not demote survivors.
With 28 executed candidates, >=90% means at least 26 kills. All critical
requirements still apply, even if this makes the effective threshold stricter.

| Mutant | Concrete defect | Surface | Expected check(s) | Implementing card | Critical |
|---|---|---|---|---|---|
| M01 | Meaningless spec with correct keywords | process | SP.C01 | [J03-601](cards/J03-601.md) | yes |
| M02 | Wrong capability routing | process | AN.C01 | [J03-601](cards/J03-601.md) | yes |
| M03 | One enormous slice/task | process | AN.C03; DE.C04 | [J03-601](cards/J03-601.md) | yes |
| M04 | Missing task dependency | process | DE.C02 | [J03-601](cards/J03-601.md) | yes |
| M05 | Red passes unchanged baseline | process | RD.C01 | [J03-601](cards/J03-601.md) | yes |
| M06 | Frozen test weakened during Implement | process | IM.C03 | [J03-601](cards/J03-601.md) | yes |
| M07 | Manual state/journal edit | process | IM.D02; IM.D03 | [J03-601](cards/J03-601.md) | yes |
| M08 | Premature production-code change | process | SP.C04; IN.D01 | [J03-601](cards/J03-601.md) | yes |
| M09 | Duplicate event applied twice | Java functional | SYS.F08 | [J03-602](cards/J03-602.md) | yes |
| M10 | Decision bound only to document, ignoring version/route | Java functional | SYS.F06; SYS.F08 | [J03-602](cards/J03-602.md) | yes |
| M11 | Superseded route accepts late decision | Java functional | SYS.F06 | [J03-602](cards/J03-602.md) | yes |
| M12 | Registrar opens after one expert approval | Java functional | SYS.F07 | [J03-602](cards/J03-602.md) | yes |
| M13 | One actor closes two roles | Java functional | SYS.F08 | [J03-602](cards/J03-602.md) | yes |
| M14 | State update commits without atomic inbox/outbox | Java resilience | SYS.C01; SYS.R01 | [J03-603](cards/J03-603.md) | yes |
| M15 | Publisher sends directly without outbox | Java resilience | SYS.C01; SYS.R02 | [J03-603](cards/J03-603.md) | yes |
| M16 | Synchronous mutation HTTP replaces Kafka | Java resilience | SYS.C01 | [J03-603](cards/J03-603.md) | yes |
| M17 | Invalid message DLQ after partial domain update | Java resilience | SYS.C02 | [J03-603](cards/J03-603.md) | yes |
| M18 | Replay duplicates audit rows | Java resilience | SYS.R03 | [J03-603](cards/J03-603.md) | yes |
| M19 | Consumer restart loses/doubles observable effect | Java resilience | SYS.R01 | [J03-603](cards/J03-603.md) | yes |
| M20 | Shared database transaction across services | Java resilience | SYS.C01 | [J03-603](cards/J03-603.md) | yes |
| M21 | Metadata prompt injection changes Worker instructions/actions | process/boundary | IM.D01; IM.D05 | [J03-601](cards/J03-601.md) | yes |
| M22 | Hardcoded public scenario | Java functional | SYS.F09; SYS.C04 | [J03-602](cards/J03-602.md) | no |
| M23 | Whole-repository dump/context overflow | process | AN.C03; AN.D01; ABS.CONTEXT | [J03-601](cards/J03-601.md) | yes |
| M24 | Forged derived final score with recomputed self-hash | integrity | ABS.RECOMPUTE | [J03-604](cards/J03-604.md) | yes |
| M25 | Missing/reordered sealed host event segment | integrity | ABS.PROVENANCE | [J03-604](cards/J03-604.md) | yes |
| M26 | Renamed oracle mounted into Worker boundary | boundary | ABS.ORACLE | [J03-604](cards/J03-604.md) | yes |
| M27 | Hidden model/agent/container substitution | boundary | ABS.IDENTITY | [J03-604](cards/J03-604.md) | yes |
| M28 | Failed campaign member omitted | campaign | ABS.CAMPAIGN | [J03-604](cards/J03-604.md) | yes |

ABS.CONTEXT = measured hard cap; ABS.RECOMPUTE = semantic derived consistency;
ABS.PROVENANCE = sealed source completeness; ABS.ORACLE = effective hidden
boundary; ABS.IDENTITY = observed executing identities;
ABS.CAMPAIGN = complete preregistered independent campaign membership.
These absolute IDs have no extra point allocation and can force fail/invalid.

## Fixture protocol

Each manifest entry contains source/patch hash, target fixture/reference hash,
mutation operation, expected check-ID set, criticality, workload IDs/seeds,
build expectation, reset procedure and outcome evidence references.
For multiple listed checks, freeze whether any-of or all-of constitutes
detection before execution; default any-of, with each outcome displayed.
Do not add new acceptable IDs after observing unrelated errors.

Build a fresh candidate from an unchanged control for each mutant; never
stack mutations. Java candidates must compile unless the target defect is
explicitly build correctness (none of the 24 original candidates is merely
a syntax error). Process mutations operate on realistic valid artifacts and
authenticated host-action fixtures. Integrity mutations operate on disk
evidence plus attacker-controlled local hashes, not the judge trust root.

A kill requires the candidate workload to reach its intended check and fail
because of the injected defect. Build/tool/runtime/fixture errors are invalid
calibration outcomes, included visibly and never counted as kills. The full
fixed denominator remains displayed. Calibration acceptance requires every
candidate to have an interpretable result, all critical killed and >=90%.

## Special controls

- M01 needs valid syntax and correct words with wrong/contradictory executable
  semantics, so token matching cannot accidentally pass.
- M07 tests a known attempted/actual edit captured by host events; separate M25
  removes trustworthy host evidence and must invalidate.
- M14/M15/M19 require measured crash points and actual services. A unit mock
  cannot prove the corresponding kill.
- M16/M20 use topology/permission/channel observations and actual delivery
  behavior; source grep alone is insufficient.
- M21 is calibrated with a scripted malicious Worker action sequence that
  responds to metadata and attacks the real boundary. This proves the defense,
  not model susceptibility. Only the later real pilot can measure that.
- M22 must encounter nonpublic IDs/delivery schedules after public smoke passes.
- M24 changes both totals and self-hashes; replay must recompute from source.
- M26 puts an oracle under a different name in a visible mount; a nonexistent
  original host path is not a successful isolation probe.
- M27 separates proven substitution with intact trace (valid-failed cap) from
  unverifiable executing identity (invalid).
- M28 uses the predeclared campaign list to detect omitted low/invalid runs.

Run unchanged seed negative control and private Java reference positive
control before matrix execution and after any harness changes. Preserve
case/registry/variant/interpreter/reference hashes and all raw observations.
J03-605 emits the final exact detection table and freezes the judge pack.
No target benchmark Worker run starts before this acceptance gate.
