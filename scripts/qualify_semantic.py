"""QF-017: semantic validation of qualification disk artifacts.

JSON Schema alone cannot express cross-field and cross-file consistency.
After schema validation, `semantic_validate_report` and
`semantic_validate_manifest` recompute what is recomputable from the artifact
itself and from the run reports on disk; a manifest is written only when both
validations pass. Independent re-computation of T1-T8 must be possible from
disk artifacts alone, without runner memory.
"""

from __future__ import annotations

import json
from pathlib import Path


class SemanticValidationError(Exception):
    """Artifact is schema-valid but internally/inter-file inconsistent."""


def _load_report(runs_root: Path, campaign_id: str, run_id: str) -> dict:
    path = runs_root / campaign_id / run_id / "report.yaml"
    if not path.is_file():
        raise SemanticValidationError(f"manifest run {run_id!r}: report.yaml missing")
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def semantic_validate_report(report: dict) -> None:
    """Cross-field recomputation for one per-run report."""
    run_id = report.get("run_id", "<unset>")
    stages = report.get("stages") or []
    calls = report.get("calls") or []
    totals = report.get("totals") or {}

    if report.get("error"):
        # infrastructure failure: measurements may be null; only the
        # error bookkeeping is recomputable
        if report.get("verdict") != "fail":
            raise SemanticValidationError(f"{run_id}: error without fail verdict")
        failures = report.get("threshold_failures") or []
        if not any(str(f).startswith("run_error:") for f in failures):
            raise SemanticValidationError(
                f"{run_id}: error present but no run_error failure recorded"
            )
        return

    passed = sum(int(s.get("checks", {}).get("passed") or 0) for s in stages)
    failed = sum(int(s.get("checks", {}).get("failed") or 0) for s in stages)
    correctness = totals.get("correctness") or {}
    if correctness.get("passed") != passed or correctness.get("failed") != failed:
        raise SemanticValidationError(
            f"{run_id}: totals.correctness {correctness!r} != recomputed "
            f"({passed} passed / {failed} failed) from stages"
        )
    expected_unique = max((int(c.get("unique_files") or 0) for c in calls), default=0)
    if totals.get("max_unique_files") != expected_unique:
        raise SemanticValidationError(
            f"{run_id}: totals.max_unique_files {totals.get('max_unique_files')!r} "
            f"!= max over calls ({expected_unique})"
        )
    # QF-017: JSON Schema cannot reject NaN (it is a JSON "number"); the
    # semantic layer must.
    for key, value in totals.items():
        if isinstance(value, float) and value != value:
            raise SemanticValidationError(f"{run_id}: totals.{key} is NaN")
    for index, call in enumerate(calls):
        for key, value in call.items():
            if isinstance(value, float) and value != value:
                raise SemanticValidationError(
                    f"{run_id}: calls[{index}].{key} is NaN"
                )
    if report.get("verdict") == "pass":
        if report.get("error"):
            raise SemanticValidationError(f"{run_id}: pass verdict carries an error")
        if report.get("threshold_failures"):
            raise SemanticValidationError(f"{run_id}: pass verdict carries failures")
        required = (
            "context_peak_tokens", "framework_input_tokens_max",
            "max_unique_files", "hallucinated_paths", "envelope_violations",
        )
        missing = [k for k in required if not isinstance(totals.get(k), int)]
        if missing:
            raise SemanticValidationError(
                f"{run_id}: pass verdict with unmeasured totals: {missing}"
            )
        if totals.get("evidence_authentic") is not True:
            raise SemanticValidationError(f"{run_id}: pass verdict without authentic evidence")
        not_completed = [
            s.get("stage") for s in stages if s.get("status") != "completed"
        ]
        if not_completed:
            raise SemanticValidationError(
                f"{run_id}: pass verdict with non-completed stages {not_completed}"
            )

def semantic_validate_manifest(
    manifest: dict,
    runs_root: Path,
    validate_report_fn=None,
    expected_total_runs: int | None = None,
) -> None:
    """Cross-file consistency for the campaign manifest.

    `validate_report_fn(kind, doc)` performs the JSON Schema half so the
    checker never accepts a report the schema rejects. Verdict recomputation
    applies only to complete campaigns; `pending`/`incomplete` are valid
    partial states (QF-017 item 5).
    """
    campaign_id = manifest.get("campaign_id")
    runs = manifest.get("runs") or []
    run_ids = [r.get("run_id") for r in runs]
    if len(set(run_ids)) != len(run_ids):
        dupes = sorted({r for r in run_ids if run_ids.count(r) > 1})
        raise SemanticValidationError(f"duplicate run IDs in manifest: {dupes}")
    cases = manifest.get("cases") or []
    for row in runs:
        if row.get("case") not in cases:
            raise SemanticValidationError(
                f"manifest run {row.get('run_id')!r}: case {row.get('case')!r} "
                f"is not in the campaign cases {cases}"
            )
    if expected_total_runs is not None and len(run_ids) != expected_total_runs:
        raise SemanticValidationError(
            f"manifest has {len(run_ids)} runs; expected {expected_total_runs}"
        )

    model_id = (manifest.get("model") or {}).get("id", {}).get("value")
    commit = (manifest.get("framework") or {}).get("commit")
    for row in runs:
        report = _load_report(runs_root, campaign_id, row["run_id"])
        if validate_report_fn is not None:
            validate_report_fn("run-report", report)
        semantic_validate_report(report)
        if report.get("framework_commit") != commit:
            raise SemanticValidationError(
                f"run {row['run_id']}: commit {report.get('framework_commit')!r} "
                f"!= campaign commit {commit!r}"
            )
        if model_id is not None and report.get("model") != model_id:
            raise SemanticValidationError(
                f"run {row['run_id']}: model {report.get('model')!r} "
                f"!= campaign model {model_id!r}"
            )
        if report.get("verdict") != row.get("verdict"):
            raise SemanticValidationError(
                f"run {row['run_id']}: manifest verdict {row.get('verdict')!r} "
                f"!= report verdict {report.get('verdict')!r}"
            )

    verdict = manifest.get("verdict")
    if verdict in ("pass", "fail") and expected_total_runs is not None:
        # recompute the campaign verdict from the per-case facts on disk
        case_verdicts = manifest.get("case_verdicts") or {}
        if set(case_verdicts) != set(cases):
            raise SemanticValidationError(
                "case_verdicts keys do not match the campaign cases"
            )
        for case, block in case_verdicts.items():
            case_runs = [r for r in runs if r.get("case") == case]
            expected = "pass" if (
                case_runs
                and all(r.get("verdict") == "pass" and not r.get("error") for r in case_runs)
                and not block.get("median_failures")
            ) else "fail"
            if block.get("verdict") != expected:
                raise SemanticValidationError(
                    f"case {case}: verdict {block.get('verdict')!r} != "
                    f"recomputed {expected!r}"
                )
        recomputed = (
            "pass"
            if all(b.get("verdict") == "pass" for b in case_verdicts.values())
            and len(run_ids) == expected_total_runs
            else "fail"
        )
        executor_kind = ((manifest.get("executor") or {}).get("kind") or {}).get("value")
        if recomputed == "pass" and executor_kind != "isolated":
            # QF-013: only the isolated boundary can produce a release pass.
            recomputed = "non-release"
        if verdict != recomputed:
            raise SemanticValidationError(
                f"manifest verdict {verdict!r} != recomputed {recomputed!r}"
            )
