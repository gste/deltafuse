# Second implementation review — 2026-09-19

Status: **acceptance open; further remediation required**.
Reviewed HEAD: `ab7778b3431a164b64c55a1b1fcdb5ed479fb88b`.
This review supersedes the latest overall completion claim. Prior reports and
card completion timestamps remain historical evidence, not current acceptance.

## Findings and cards

| Finding | Verified issue | New card |
|---|---|---|
| 1 | Wheel lacks the operation-envelope schema; isolated artifact create fails | [AW-29](cards/AW-29.md) |
| 2 | CLI writes to an archived Change; commit revalidation uses cached authority | [AW-30](cards/AW-30.md) |
| 3 | Version 99.99.99 and an all-zero content hash still permit writes | [AW-31](cards/AW-31.md) |
| 4 | Public Writer process commits while Core product lock is held | [AW-32](cards/AW-32.md) |
| 5 | Injected post-publication corruption still receives a committed receipt | [AW-33](cards/AW-33.md) |
| 6 | First-file slice inference and malformed prerequisite metadata are accepted | [AW-34](cards/AW-34.md) |
| 7 | Substring-based oracle scores an invalid task semantically correct | [AW-35](cards/AW-35.md) |
| 8 | Live paired-model evaluation and required platform qualification remain open despite closure | [AW-36](cards/AW-36.md) |

## Observed verification

All Artifact Writer test modules ran: **145 passed, 2 skipped** (symlink
privileges), exit 0. Asset synchronization passed for 57 assets. The review
also ran public service/CLI adversarial probes for findings 1–7. Post-publication
corruption was fault injection; lock contention used separate OS processes.

The existing wheel was extracted outside the checkout and executed without a
source import path. Its registry and CLI bytes matched reviewed HEAD, but it
contained no `artifact-writer.schema.yaml`; artifact create exited 1 with
`ArtifactRegistryError`. Wheel SHA256:
`9899dfb11cd459b4f0de5d1a5f30ca23db07cf15e4748f9fc50c8902eb75b5f7`.

The oracle probe used a task containing `id: WRONG`, `kind: INVALID` and
`slice: MISSING`; it returned `semantic_correct: true`. Source inspection found
no actual `check_gate` invocation in that oracle, despite the completion report.

The review used bundled Python with repository source and existing venv packages,
bytecode/cache disabled and a writable temporary test base. It did not rerun
the full framework suite, smoke/layout matrix or POSIX qualification. No runtime
files were changed. This is a review-session summary, not a new immutable
qualification result; remediation executors must capture their own exact Red,
Green, runtime and evidence identities under EXECUTOR.md.

## Current queue and acceptance

`AW-29 -> AW-30 -> AW-31 -> AW-32 -> AW-33 -> AW-34 -> AW-35 -> AW-36 -> AW-20`.

The only initially ready card is AW-29. AW-20 is reopened. Earlier statuses and
results remain historical; the mapped new cards supersede their disputed claims.
Do not treat a completed historical card as proof that a new invariant passes.

AW-36 must be split into bounded platform and live-evaluation child cards before
execution. Both must qualify the final implementation. Missing endpoint access,
mandatory platform/privilege skips, incomplete wheel operations and inconclusive
required benefit remain open. Neither a renamed harness nor a green unit suite
can satisfy these live requirements. Final closure requires independent evidence
reconciliation by reopened AW-20, with no silent waiver of original criteria.
