# AW-36b — Run paired evaluation using small-model adapter and replace synthetic evaluation score

Status: completed
Phase: I (second-review remediation child card)
Parent: [AW-36](AW-36.md)
Depends on: [AW-36a](AW-36a.md)
[Execution protocol](../EXECUTOR.md) · [Contract](../CONTRACT.md) · [Review](../REVIEW-2.md)

## Finding and invariant

Synthetic or missing evaluation scores must be replaced with actual model evidence using a registered small-model adapter, without altering the AW-35 independent oracle.

## Allowed writes

- `scripts/evaluate_artifact_writer.py`
- `tests/unit/test_artifact_writer_eval.py`
- `backlog/schema-driven-artifact-writer/evaluation/**`
- `backlog/schema-driven-artifact-writer/results/AW-36b.md`

## Steps

1. Preregister small-model adapter and model identity (`small_model_v1`).
2. Run paired evaluation across all 8 corpus strata comparing Arm A (Manual Raw YAML) and Arm B (Typed Artifact Writer).
3. Evaluate both arms using the unchanged AW-35 independent semantic and Core gate oracle.
4. Record exact paired metrics, mechanical retries, first-pass rates, and model evidence.

## Verification

Report actual model evidence with paired structural/semantic metrics without synthetic score substitution or oracle modification.
