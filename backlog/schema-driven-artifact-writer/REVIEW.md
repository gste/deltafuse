# Implementation review and remediation — 2026-09-19

Status: **acceptance open; implementation is not finished**.
Reviewed HEAD: `bbec79387e8fb0f26dbdd0e18cad5273ce26eeb2`.
This review supersedes the overall completion claim in RESULT.md. Prior card
results and evaluation evidence remain historical records, not proof of closure.

## Findings and new cards

| Finding | Observed gap | Remediation |
|---|---|---|
| 1 | Worker-authorized update wrote outside its Change; policy omits scope and live envelope checks | [AW-21](cards/AW-21.md) |
| 2 | Empty task payload committed invented semantics and unresolved references | [AW-22](cards/AW-22.md) |
| 3 | CLI accepted duplicate JSON keys and an unknown envelope field | [AW-23](cards/AW-23.md) |
| 4 | Malformed lock did not prevent creation; receipt schema hashes are zeros and timestamp is fixed | [AW-24](cards/AW-24.md) |
| 5 | Identical update retry fails stale_target; different creation body reuses old receipt | [AW-25](cards/AW-25.md) |
| 6 | Journals/receipts are directly rewritten; Writer/Core lock roots differ; evidence bypasses shared persistence | [AW-26](cards/AW-26.md) |
| 7 | Fixed-input service harness is reported as an external paired-model evaluation without independent semantic oracle | [AW-27](cards/AW-27.md) |
| 8 | Required real POSIX/platform/hard-crash qualification is not established by the completion report | [AW-28](cards/AW-28.md) |

## Evidence scope

The review ran 40 focused tests: **39 passed, 1 skipped** (symlink privileges).
The asset synchronization check passed for 57 assets. Direct temporary-directory
probes reproduced findings 1–5 through service/CLI calls. Source inspection
established the persistence and evaluation gaps. No runtime changes were made.

Focused test modules:

- `tests/unit/test_artifact_service.py`
- `tests/unit/test_artifact_policy.py`
- `tests/unit/test_artifact_recovery.py`
- `tests/unit/test_artifact_cli.py`
- `tests/integration/test_artifact_security.py`
- `tests/integration/test_artifact_crash_recovery.py`
- `tests/e2e/test_artifact_workflow.py`
- `tests/unit/test_artifact_writer_eval.py`

The repository venv launcher was unavailable to the review sandbox. Tests used
the bundled Python runtime with repository source and existing venv packages,
a writable temporary base, bytecode disabled and pytest cache disabled.
The default pytest temporary directory initially failed on permissions; that
setup failure is not a product defect. The corrected run exited 0.

The review did not rerun the full suite, smoke/layout checks or POSIX qualification.
This summary records the session findings, not a hash-indexed qualification run.
Each remediation must reproduce its own behavioral Red and save exact new
commands, runtime identities and immutable evidence under EXECUTOR.md.

## Live queue and closure

Execution order:
`AW-21 -> AW-22 -> AW-23 -> AW-24 -> AW-25 -> AW-26 -> AW-28 -> AW-27 -> AW-20`.

AW-00 through AW-19 retain their historical implementation statuses. Their
disputed acceptance claims are superseded by the mapped remediation cards;
they must not be used to skip new checks. AW-20 is reopened and depends on the
new qualification and evaluation evidence. The next ready card is AW-21.

AW-26 may need dependency-ordered child cards for its multiple Core callers.
Keep its parent open until every original requirement is covered. AW-27 cannot
substitute synthetic model results for unavailable endpoint access. AW-28 cannot
close missing mandatory platforms with mocks or skips. An inconclusive or failed
required benefit criterion remains open at final acceptance even if honestly
reported by the experiment.
