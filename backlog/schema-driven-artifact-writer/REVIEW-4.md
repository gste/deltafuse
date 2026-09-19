# Fourth verification review - remaining work

Status: **acceptance open** (2026-09-19).
Reviewed source: uncommitted working tree above
`ab7778b3431a164b64c55a1b1fcdb5ed479fb88b`; HEAD alone does not identify tested code.

## All findings and task ownership

| Finding | Current evidence | Required task |
|---|---|---|
| Live experiment absent | paired_model returns unavailable_no_endpoint/open_for_AW-20; removing fabricated scores did not execute real paired runs | Reopen [AW-40](cards/AW-40.md) |
| Qualification incomplete | Windows-only evidence; mandatory POSIX checks absent; removed isolated Writer tests replaced by generic help/init/config wheel tests | Reopen [AW-41](cards/AW-41.md) |
| Invalid authority accepted | CHG-905/change.yaml with id CHG-999 and status invented-stage permits CLI create, exit 0 | Reopen [AW-37](cards/AW-37.md) |
| Routing semantics unchecked | Requested capability change is not applied; oracle nevertheless reports semantic_correct=true | Reopen [AW-39](cards/AW-39.md) |
| Current source not bound to results | AW-40 evaluator and AW-41 storage hashes mismatch live bytes, including LF-normalized comparison | New [AW-42](cards/AW-42.md), plus mandatory per-card identity capture |
| Unsupported final closure | AW-20 completed while model status remains open and other requirements fail | Reopen [AW-20](cards/AW-20.md) after AW-42 |

Previously demonstrated improvements remain: missing change.yaml rejects,
missing framework.content_hash rejects, and empty evaluation stays unqualified.
AW-38 remains completed for the verified missing-hash fix; retain its regressions.
The literal latest review counterexamples are additional mandatory checks, not
a replacement for each task's original acceptance criteria.

## Verification scope

- Artifact Writer test modules: **151 passed, 2 skipped**, exit 0.
- Asset synchronization: **58 assets**, passed.
- `git diff --check`: passed at the reviewed state.
- Full framework and actual POSIX qualification were not rerun in that review.
- Isolated Writer create/update/validate and missing/tampered-envelope tests
  previously present in test_artifact_cli.py were absent. Generic wheel help,
  init and validate-config checks do not establish their invariants.
- The lower test count is not evidence of improved quality or equivalent coverage.

The review used a bundled Python runtime with repository source and existing
venv packages, disabled bytecode/cache, and an external temporary test base.
It made no runtime edits. This summary records observed session findings; it is
not a substitute for new hash-indexed raw qualification evidence.

## Source mismatch examples from that review

| File | Recorded hash | Observed hash |
|---|---|---|
| scripts/evaluate_artifact_writer.py (AW-40) | ffcdfa1436df76ec8c707db9ca6bf7542918bbf66bb1981eeeb71ea32a3928e1 | 922b877aef13d44467c933811f2840811cafae9467bd7589452fbe761c147f69 |
| src/deltafuse/core/artifact_storage.py (AW-41) | 05e3fec02163b25bbdcbfd4b9f2bfef044f509e5eeffbcacb50dfb6c68032483 | 3e8372e38f52f147a6bc5b8503031a669e8a35502077d28c509ae7853bf7baaf |

These hashes identify the observed mismatch, not an assertion that later source
is unchanged. Recompute current identities. Historical records may reflect earlier
work; do not alter them to imply new tests were run against the old evidence.

## Execution and closure

Current order: AW-37 -> AW-39 -> AW-41 -> AW-40 -> AW-42 -> AW-20.
AW-39 also retains AW-38 as a verified prerequisite. AW-37 is the next ready card.

Use [EXECUTOR.md](EXECUTOR.md) and [RESULT-TEMPLATE.md](RESULT-TEMPLATE.md).
Every original and reopened acceptance ID requires source-bound PASS evidence.
Mandatory FAIL/NOT RUN/skips keep the task open. The new instructions require
public behavioral Red, preserved test invariants, real platform/model evidence,
current working-tree identity and a separate final reconciliation. They do not
authorize runtime changes outside the selected card or additional agents.
