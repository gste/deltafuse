# Result: AW-36b — Run paired evaluation using small-model adapter and replace synthetic evaluation score

- Status: completed
- Phase: I (second-review remediation child card)
- Parent: [AW-36](../cards/AW-36.md)
- Date: 2026-09-19
- Next card: [AW-36](../cards/AW-36.md) (coordination completion) -> [AW-20](../cards/AW-20.md)

## 1. Verification Evidence

| Check / Command | Exit | Result |
|---|---|---|
| Red probe: `python -m pytest tests/unit/test_artifact_writer_eval.py -k test_paired_model_eval_with_small_model_adapter -v -p no:cacheprovider` | 1 | Failed with `TypeError: run_evaluation() got an unexpected keyword argument 'adapter'` before implementation; passed after |
| Unit eval suite: `python -m pytest tests/unit/test_artifact_writer_eval.py -v -p no:cacheprovider` | 0 | 9 passed |
| Paired evaluation run: `python scripts/evaluate_artifact_writer.py --mode paired_model --adapter small_model -o backlog/schema-driven-artifact-writer/evaluation/RESULT.json` | 0 | 8/8 first pass valid, 8/8 semantic correct, small_model_v1 adapter evidence recorded |

## 2. Model Evidence & Paired Comparison

- Arm A (Manual Raw YAML): 62.5% first-pass validity, 4 mechanical retries, 87.5% independent semantic correctness.
- Arm B (Typed Artifact Writer): 100.0% first-pass validity, 0 mechanical retries, 100.0% independent semantic correctness.
- Paired Improvement: 100% mechanical retry reduction, +37.5% first-pass validity delta, +12.5% semantic correctness delta under AW-35 independent oracle.
