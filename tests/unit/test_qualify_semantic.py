"""QF-017: strict schemas + semantic validation — an incomplete or
contradictory artifact is never written as release evidence; every T1-T8
input can be recomputed from disk files alone."""

from __future__ import annotations

import copy
import sys

import pytest

sys.path.insert(0, "scripts")
sys.path.insert(0, "src")

import qualify  # noqa: E402
import qualify_semantic  # noqa: E402

COMMIT = "a" * 40
MODEL = "ornith-1.5-35b-a3b"


def _valid_report() -> dict:
    from qualify_evidence import LIFECYCLE as _LC

    return {
        "schema_version": 1,
        "run_id": "camp-M01-cooldown-run1",
        "case": "M01-cooldown",
        "framework_commit": COMMIT,
        "model": MODEL,
        "verdict": "pass",
        "threshold_failures": [],
        "process": 100.0,
        "correctness": 100.0,
        "points": {"earned": 21, "max": 21},
        "executor_kind": "isolated",
        "stages": [
            {"stage": name, "status": "completed",
             "checks": {"passed": 3, "failed": 0}, "gate_retries": 0}
            for name in _LC
        ],
        "calls": [{
            "input_tokens": 9120,
            "framework_input_tokens": 6400,
            "framework_input_chars": 25600,
            "framework_input_tokens_method": "host-tokenize",
            "unique_files": 0,
            "hallucinated_paths": 0,
            "envelope_violations": 0,
        }],
        "tool_events": [],
        "totals": {
            "correctness": {"passed": 21, "failed": 0},
            "gate_retries": 0,
            "context_peak_tokens": 9120,
            "framework_input_tokens_max": 6400,
            "max_unique_files": 0,
            "hallucinated_paths": 0,
            "envelope_violations": 0,
            "evidence_authentic": True,
        },
        "framework_input_tokens_method": "host-tokenize",
        "t7_breakdown": {"write_denied": 0, "leash_violations": 0,
                         "unjournaled_change": 0, "inventory_tampered": 0,
                         "staging_escape": 0, "execution_policy": 0},
        "hallucinated_breakdown": {"hallucinated": 0, "envelope": 0,
                                   "execution_policy": 0},
        "stage_leash": [],
        "defense_checks": {
            "journal_forgery": {"id": "defense.journal_forgery", "pass": True,
                                "detail": "journals consistent"},
            "synthetic_evidence": {"id": "defense.synthetic_evidence",
                                   "pass": True, "detail": "stamps authentic"},
            "oracle_leak": {"id": "defense.oracle_leak", "pass": True,
                            "detail": "no hidden markers"},
        },
        "thresholds": {
            "source": "backlog/product/v3/thresholds.md",
            "revision": "r",
            "absolute": {
                "correctness_failed": 0, "stages_completed": 7,
                "gate_retries_max": 2, "context_peak_tokens_max": 32768,
                "framework_input_tokens_max": 16000, "max_unique_files": 24,
                "hallucinated_paths": 0, "envelope_violations": 0,
                "evidence_authentic": True,
            },
        },
    }


# ------------------------------------------------------- schema mutations


def test_calls_empty_object_rejected():
    report = _valid_report()
    report["calls"] = [{}]
    with pytest.raises(qualify.SchemaValidationError):
        qualify.validate_document("run-report", report)


@pytest.mark.parametrize("field", [
    "input_tokens", "framework_input_chars", "framework_input_tokens",
    "framework_input_tokens_method", "unique_files", "hallucinated_paths",
    "envelope_violations",
])
def test_call_missing_each_measurement_rejected(field):
    report = _valid_report()
    del report["calls"][0][field]
    with pytest.raises(qualify.SchemaValidationError):
        qualify.validate_document("run-report", report)


def test_call_extra_field_rejected():
    report = _valid_report()
    report["calls"][0]["sneaky"] = 1
    with pytest.raises(qualify.SchemaValidationError):
        qualify.validate_document("run-report", report)


@pytest.mark.parametrize("bad", ["many", True])
def test_call_wrong_type_rejected(bad):
    report = _valid_report()
    report["calls"][0]["input_tokens"] = bad
    with pytest.raises(qualify.SchemaValidationError):
        qualify.validate_document("run-report", report)


def test_pass_with_null_measurement_rejected():
    report = _valid_report()
    report["totals"]["context_peak_tokens"] = None
    with pytest.raises(qualify.SchemaValidationError):
        qualify.validate_document("run-report", report)


def test_pass_with_error_rejected():
    report = _valid_report()
    report["error"] = {"class": "io_error", "detail": "boom"}
    with pytest.raises(qualify.SchemaValidationError):
        qualify.validate_document("run-report", report)


def test_fail_without_failures_rejected():
    report = _valid_report()
    report["verdict"] = "fail"
    with pytest.raises(qualify.SchemaValidationError):
        qualify.validate_document("run-report", report)


def test_valid_pass_and_infra_fail_accepted():
    qualify.validate_document("run-report", _valid_report())
    infra = _valid_report()
    infra["verdict"] = "fail"
    infra["stages"] = []
    infra["calls"] = []
    infra["totals"].update({
        "correctness": {"passed": None, "failed": None},
        "gate_retries": None, "context_peak_tokens": None,
        "framework_input_tokens_max": None, "max_unique_files": None,
        "hallucinated_paths": None, "envelope_violations": None,
        "evidence_authentic": False,
    })
    infra["threshold_failures"] = ["run_error:score_error"]
    infra["error"] = {"class": "score_error", "detail": "boom"}
    qualify.validate_document("run-report", infra)


# ------------------------------------------------- semantic re-computation


def test_semantic_inconsistent_totals_rejected():
    report = _valid_report()
    report["totals"]["correctness"]["passed"] = 20  # stages sum to 21
    with pytest.raises(qualify_semantic.SemanticValidationError):
        qualify_semantic.semantic_validate_report(report)


def test_semantic_nan_rejected():
    report = _valid_report()
    report["totals"]["context_peak_tokens"] = float("nan")
    with pytest.raises(qualify_semantic.SemanticValidationError, match="NaN"):
        qualify_semantic.semantic_validate_report(report)


def _manifest(tmp_path, report=None, runs=None):
    report = report or _valid_report()
    run_dir = tmp_path / "camp" / report["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    import yaml
    (run_dir / "report.yaml").write_text(yaml.safe_dump(report), encoding="utf-8")
    summary = {k: report[k] for k in ("run_id", "case", "verdict", "threshold_failures")}
    manifest = {
        "schema_version": 1,
        "campaign_id": "camp",
        "created": "2026-09-13T00:00:00Z",
        "framework": {"commit": COMMIT, "lock_hash": "sha256:" + "0" * 64},
        "executor": {
            "kind": {"value": "isolated", "provenance": "declared", "basis": "b"},
            "boundary": {"value": "container", "provenance": "declared", "basis": "b"},
            "network_policy": {"value": "none", "provenance": "declared", "basis": "b"},
            "boundary_probe": {"value": [{"run": "r"}], "provenance": "measured",
                               "method": "in-container probe"},
        },
        "model": {"id": {"value": MODEL, "provenance": "measured", "method": "m"}},
        "thresholds": {
            "source": "s", "revision": "r",
            "absolute": {
                "correctness_failed": 0, "stages_completed": 7,
                "gate_retries_max": 2, "context_peak_tokens_max": 32768,
                "framework_input_tokens_max": 16000, "max_unique_files": 24,
                "hallucinated_paths": 0, "envelope_violations": 0,
                "evidence_authentic": True,
            },
        },
        "cases": ["M01-cooldown"],
        "runs": runs if runs is not None else [summary],
        "case_verdicts": {
            "M01-cooldown": {
                "verdict": "pass",
                "medians": {
                    "correctness": 100.0, "process": 100.0,
                    "context_peak_tokens": 9120.0,
                    "framework_input_tokens_max": 6400.0,
                    "framework_input_chars_max": 25600.0,
                    "gate_retries": 0.0, "max_unique_files": 0.0,
                    "hallucinated_paths": 0.0, "envelope_violations": 0.0,
                },
                "median_failures": [],
            }
        },
        "verdict": "pass",
    }
    return manifest, summary


def _validate_manifest(tmp_path, manifest):
    qualify_semantic.semantic_validate_manifest(
        manifest, tmp_path,
        validate_report_fn=qualify.validate_document,
        expected_total_runs=1,
    )


def test_semantic_manifest_complete_campaign_passes(tmp_path):
    manifest, _ = _manifest(tmp_path)
    _validate_manifest(tmp_path, manifest)


def test_semantic_duplicate_run_id_rejected(tmp_path):
    manifest, summary = _manifest(tmp_path)
    manifest["runs"] = [summary, dict(summary)]
    with pytest.raises(qualify_semantic.SemanticValidationError, match="duplicate"):
        _validate_manifest(tmp_path, manifest)


def test_semantic_missing_report_rejected(tmp_path):
    manifest, _ = _manifest(tmp_path)
    (tmp_path / "camp" / manifest["runs"][0]["run_id"] / "report.yaml").unlink()
    with pytest.raises(qualify_semantic.SemanticValidationError, match="missing"):
        _validate_manifest(tmp_path, manifest)


def test_semantic_commit_mismatch_rejected(tmp_path):
    manifest, _ = _manifest(tmp_path)
    manifest["framework"]["commit"] = "b" * 40
    with pytest.raises(qualify_semantic.SemanticValidationError, match="commit"):
        _validate_manifest(tmp_path, manifest)


def test_semantic_model_mismatch_rejected(tmp_path):
    manifest, _ = _manifest(tmp_path)
    manifest["model"]["id"]["value"] = "other-model"
    with pytest.raises(qualify_semantic.SemanticValidationError, match="model"):
        _validate_manifest(tmp_path, manifest)


def test_semantic_tampered_verdict_rejected(tmp_path):
    manifest, _ = _manifest(tmp_path)
    report = _valid_report()
    report["verdict"] = "fail"
    report["threshold_failures"] = ["T1 correctness_failed=1"]
    report["totals"]["correctness"]["failed"] = 1
    manifest["runs"][0]["verdict"] = "fail"
    manifest["case_verdicts"]["M01-cooldown"]["verdict"] = "pass"
    manifest["verdict"] = "pass"
    run_dir = tmp_path / "camp" / report["run_id"]
    import yaml
    (run_dir / "report.yaml").write_text(yaml.safe_dump(report), encoding="utf-8")
    with pytest.raises(qualify_semantic.SemanticValidationError):
        _validate_manifest(tmp_path, manifest)


def test_semantic_local_dev_cannot_release_pass(tmp_path):
    manifest, _ = _manifest(tmp_path)
    manifest["executor"]["kind"]["value"] = "local-dev"
    with pytest.raises(qualify_semantic.SemanticValidationError,
                       match="non-release|executor kind mismatch"):
        _validate_manifest(tmp_path, manifest)


def test_semantic_run_count_mismatch_rejected(tmp_path):
    manifest, _ = _manifest(tmp_path)
    manifest["runs"] = []
    with pytest.raises(qualify_semantic.SemanticValidationError, match="expected"):
        _validate_manifest(tmp_path, manifest)
