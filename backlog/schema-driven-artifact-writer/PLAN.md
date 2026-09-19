# Implementation plan Р В Р’В Р В РІР‚В Р В Р’В Р Р†Р вЂљРЎв„ўР В Р вЂ Р В РІР‚С™Р РЋРЎС™ Schema-driven Artifact Writer

Status: **implementation requires remediation; acceptance open**.
The original phase plan below is historical. See [REVIEW-6.md](REVIEW-6.md)
for reopened tasks, strengthened execution rules and evidence reconciliation.
Baseline: canonical repository VERSION 3.1.0,
17786cb040d1ed3cd5636dd4a6b97453c1b77627 (2026-09-18).
Read [INTENTION.md](INTENTION.md), [ANALYSIS.md](ANALYSIS.md) and
[CONTRACT.md](CONTRACT.md) as intent, current findings and proposed design.

## Delivery boundaries

| Phase | Cards | Result |
|---|---|---|
| A contracts/readers | AW-00Р В Р’В Р В РІР‚В Р В Р’В Р Р†Р вЂљРЎв„ўР В Р вЂ Р В РІР‚С™Р РЋРЎв„ў03 | Explicit supported kinds, authority, strict decoding and pinned schema resolution |
| B transformation/policy | AW-04Р В Р’В Р В РІР‚В Р В Р’В Р Р†Р вЂљРЎв„ўР В Р вЂ Р В РІР‚С™Р РЋРЎв„ў06 | Canonical codec, safe patch semantics, actual Core authorization |
| C persistence | AW-07Р В Р’В Р В РІР‚В Р В Р’В Р Р†Р вЂљРЎв„ўР В Р вЂ Р В РІР‚С™Р РЋРЎв„ў09 | No-overwrite create, atomic update, CAS/locking and recoverable receipts |
| D public interface | AW-10Р В Р’В Р В РІР‚В Р В Р’В Р Р†Р вЂљРЎв„ўР В Р вЂ Р В РІР‚С™Р РЋРЎв„ў11 | Shared Python service, CLI and small tool argument schemas |
| E Core callers | AW-12Р В Р’В Р В РІР‚В Р В Р’В Р Р†Р вЂљРЎв„ўР В Р вЂ Р В РІР‚С™Р РЋРЎв„ў14 | Authentic verification evidence, status/Gate persistence, valid scaffold/index handling |
| F rollout/qualification | AW-15Р В Р’В Р В РІР‚В Р В Р’В Р Р†Р вЂљРЎв„ўР В Р вЂ Р В РІР‚С™Р РЋРЎв„ў17 | Synchronized skills/assets/docs, manual compatibility and real platform checks |
| G measured benefit | AW-18Р В Р’В Р В РІР‚В Р В Р’В Р Р†Р вЂљРЎв„ўР В Р вЂ Р В РІР‚С™Р РЋРЎв„ў20 | Controlled smaller-model experiment and acceptance closure |

Default sequence is deliberately linear for a smaller implementation model.
Each card has one bounded responsibility and Red/Green criteria. If a card
cannot fit one session, split it into child cards with preserved dependencies
and acceptance rather than skipping difficult behavior.

Do not apply the J03 benchmark's old Wave 3 gate or require Java/Docker product
qualification for this independent feature. Recheck current repository health
and preserve concurrent work at AW-00. This plan contains no product-specific
behavior; examples are framework artifact operations only.

## Ordered queue

| Card | Work | Depends on |
|---|---|---|
| [AW-00](cards/AW-00.md) | Freeze the artifact and authority catalog | baseline review |
| [AW-01](cards/AW-01.md) | Define typed operation and receipt contracts | AW-00 |
| [AW-02](cards/AW-02.md) | Implement strict bounded input and artifact readers | AW-01 |
| [AW-03](cards/AW-03.md) | Resolve pinned schemas and structured validation | AW-02 |
| [AW-04](cards/AW-04.md) | Implement deterministic YAML/frontmatter codec | AW-03 |
| [AW-05](cards/AW-05.md) | Implement typed patches and immutable-field protection | AW-04 |
| [AW-06](cards/AW-06.md) | Bind Core authorization, paths and source identity | AW-05 |
| [AW-07](cards/AW-07.md) | Implement single-file atomic publication primitives | AW-06 |
| [AW-08](cards/AW-08.md) | Implement mutation locking and optimistic concurrency | AW-07 |
| [AW-09](cards/AW-09.md) | Implement durable receipts, idempotency and crash recovery | AW-08 |
| [AW-10](cards/AW-10.md) | Assemble the typed Artifact Writer service | AW-09 |
| [AW-11](cards/AW-11.md) | Expose CLI and small tool-call schemas | AW-10 |
| [AW-12](cards/AW-12.md) | Integrate Core execution evidence including verification | AW-11 |
| [AW-13](cards/AW-13.md) | Integrate status and Human Gate persistence safely | AW-12 |
| [AW-14](cards/AW-14.md) | Repair scaffold and integrate derived indexes | AW-13 |
| [AW-15](cards/AW-15.md) | Synchronize docs, skills, templates and packaged assets | AW-14 |
| [AW-16](cards/AW-16.md) | Prove backwards compatibility and full workflow integration | AW-15 |
| [AW-17](cards/AW-17.md) | Run security, crash and platform acceptance matrix | AW-16 |
| [AW-18](cards/AW-18.md) | Build paired small-model evaluation protocol and corpus | AW-17 |
| [AW-19](cards/AW-19.md) | Run paired external small-model evaluation | AW-18 |
| [AW-20](cards/AW-20.md) | Close acceptance and publish migration/handoff | AW-19 |

Machine-readable status: [queue.json](queue.json). Next ready card: AW-45.
Current order: AW-45 -> AW-41 -> AW-40 -> AW-42 -> AW-20 (AW-43 and AW-44
completed with evidence; AW-38/AW-39 remain completed; preserve their
regressions). AW-41 is dependency-ready after AW-45 but environmentally
blocked (native POSIX host / symlink privileges).
Prior implementation statuses are historical; new cards must satisfy the
original acceptance requirements before the feature can be marked complete.

## Design decisions to carry into implementation

- JSON typed interchange; YAML/Markdown storage retained.
- Schema registry reused, with operation-specific authority/field descriptors.
- Worker status, decision acceptance and evidence truth never become patchable.
- Core service is deterministic, not another runtime role.
- Full candidate validation before publication, read-back after publication.
- Whole-file expected hash, shared Core mutation lock, no-replace create.
- Multi-file journal/receipt recovery explicit; one rename is not a transaction.
- Unpatched values and body bytes preserved; metadata canonicalization requires
  explicit per-hash opt-in on legacy formatting/comments.
- Inherited schema versions respected; no universal generated metadata.
- Existing manually maintained valid artifacts remain usable.
- Same independent semantic/gate oracle in raw and writer evaluation arms.

These are proposed implementation contracts. AW-00 freezes any remaining
compatibility decisions with their rationale; routine details need no extra
permission. Material changes to existing authority or supported artifact
formats require an explicit reviewed contract decision, not inferred defaults.

## Result and commit structure

Use results/<AW-ID>.md for each card, recording source identities,
commands/exits, Red/Green/regression, platform evidence and remaining limits.
Raw evidence goes to an operator-selected external location with immutable
hash-indexed references; no secrets/machine-specific paths in tracked files.
Use small reviewed implementation commits when authorized. This planning task
does not stage or commit anything.

Suggested groups: contracts/readers; codec/policy; atomic persistence; public
API; Core evidence/transitions/indexes; synchronized assets/docs; evaluation.
Never combine all runtime and evidence changes into an unreviewable megacommit.

Final acceptance is in [VALIDATION.md](VALIDATION.md). No weaker-model benefit
claim until actual paired results exist. Do not declare code complete if
status/evidence bypass, crash recovery or mandatory platform checks remain open.

## Sixth-review remediation cards

- [AW-43](cards/AW-43.md): literal criteria, compound parent statuses and unsupported claims. **Completed 2026-09-19** (results/AW-43.md).
- [AW-44](cards/AW-44.md): real isolated wheel qualification and retrievable evidence. **Completed 2026-09-19** (results/AW-44.md, evidence/reconciliation/AW-44/).
- [AW-45](cards/AW-45.md): queue/handoff consistency checker with negative fixtures. **Completed 2026-09-19** (results/AW-45.md, check_backlog.py).

AW-41 additionally depends on AW-44/AW-45; existing live platform and model
requirements retain their original owning cards.
