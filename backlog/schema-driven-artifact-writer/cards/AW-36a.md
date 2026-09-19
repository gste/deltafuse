# AW-36a — Complete platform crash, lock and release qualification

Status: completed
Phase: I (second-review remediation child card)
Parent: [AW-36](AW-36.md)
Depends on: [AW-35](AW-35.md)
[Execution protocol](../EXECUTOR.md) · [Contract](../CONTRACT.md) · [Review](../REVIEW-2.md)

## Finding and invariant

Platform qualification requires verifiable real subprocess execution, lock contention, hard-crash recovery, layout validation, and isolated wheel verification.

## Allowed writes

- `tests/integration/test_artifact_crash_recovery.py`
- `tests/integration/test_artifact_locking.py`
- `tests/integration/test_artifact_security.py`
- `backlog/schema-driven-artifact-writer/evidence/platform/**`
- `backlog/schema-driven-artifact-writer/results/AW-36a.md`

## Steps

1. Run public-operation concurrency and hard-crash tests on Windows and available POSIX filesystems.
2. Run full pytest suite, smoke tests (`tests/smoke-test.ps1`), layout validator (`tests/validate-layout.ps1`), asset drift check (`scripts/sync_assets.py --check`).
3. Verify isolated wheel execution without checkout fallback.

## Verification

All platform qualification checks pass with clean exit codes and recorded command identities.
