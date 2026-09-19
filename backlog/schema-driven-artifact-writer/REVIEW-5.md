# Fifth verification review - exact remaining acceptance gaps

Status: **acceptance open**, 2026-09-19.
Reviewed clean commit: `60415a9071826d1c0a7781cccdcc743175b485bf`.

| Finding | Evidence from review | Task ownership |
|---|---|---|
| Missing Change identity still permits mutation | change.yaml containing only status: normalized allowed CLI create, exit 0; identity guard checks mismatch only when an ID is present | Reopen [AW-37](cards/AW-37.md), AW37-F1/F2 |
| Real model experiment is absent | Evaluator reports open_for_AW-20; result table substitutes oracle use/honest absence reporting for actual fresh paired sessions | Reopen [AW-40](cards/AW-40.md), AW40-F1/F2 |
| Required POSIX/capable-host execution absent | Only Windows evidence and mandatory privilege skips accompany a Windows/POSIX PASS claim | Reopen [AW-41](cards/AW-41.md), AW41-F1 |
| Wrong packaged-schema negative test | Test named missing_and_tampered_envelope exercises missing JSON fields and a stale expected_sha256; it never removes/corrupts the installed schema asset | Reopen [AW-41](cards/AW-41.md), AW41-F2/F3/F4 |
| Reconciliation and closure overstate acceptance | PASS tables narrow original requirements; model/platform/package invariants remain unmet | Reopen [AW-42](cards/AW-42.md) and [AW-20](cards/AW-20.md) |

Verified progress: the wrong-ID/unknown-stage probe now denies; the ignored routing
patch now fails the oracle; all 10 source hashes in AW-42 match the reviewed tree.
AW-38 and AW-39 remain completed for their demonstrated fixes; preserve regressions.

Focused tests rerun: **50 passed, 2 skipped** across policy, registry, service,
oracle and security. Asset synchronization passed for 58 assets; diff checks
passed. Full framework/platform/wheel qualification was not rerun in this review.
These observations are a review summary, not replacement raw qualification logs.

## Current execution sequence

AW-37 -> AW-41 -> AW-40 -> AW-42 -> AW-20.
AW-41 also retains completed AW-39 as a dependency. Only AW-37 is initially ready.
Reopened tasks keep all earlier requirements and add the fifth-review checks.
Do not create another task merely to rename an unmet requirement as completed.

## Why stronger instructions are required

Previous result tables marked different, weaker statements PASS:

- Original AW40-R2 required real model/provider identity and actual fresh sessions
  for manual and Writer arms; the report cited use of an oracle instead.
- Original AW41-R3 required actual Windows and POSIX checks; the report cited
  Windows runs and disclosure of skipped privileges.
- Installed-schema corruption coverage became malformed request/hash coverage.

These substitutions cannot satisfy the original criteria, regardless of test
counts or honest disclaimers. Use [EXECUTOR.md](EXECUTOR.md), preserve criterion
text verbatim in [RESULT-TEMPLATE.md](RESULT-TEMPLATE.md), and apply
[RECONCILIATION-CHECKLIST.md](RECONCILIATION-CHECKLIST.md) before any completion.
No instruction in this update waives real model/POSIX evidence or authorizes
new external services, additional agents, runtime edits or commits implicitly.
