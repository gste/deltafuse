"""QF-008: JSON Schema validation of qualification artifacts."""

from __future__ import annotations

import sys

import pytest

sys = pytest.importorskip("sys")
sys.path.insert(0, "scripts")

import qualify  # noqa: E402


def _full_report() -> dict:
    return {
        "schema_version": 1,
        "run_id": "camp-M01-cooldown-run1",
        "case": "M01-cooldown",
        "framework_commit": "a" * 40,
        "model": qualify.REFERENCE_MODEL_ID,
        "verdict": "pass",
        "threshold_failures": [],
        "process": 100.0,
        "correctness": 100.0,
        "stages": [
            {
                "stage": "intake",
                "status": "completed",
                "checks": {"passed": 3, "failed": 0},
                "gate_retries": 0,
            }
        ],
        "calls": [
            {
                "input_tokens": 9120,
                "framework_input_tokens": 6400,
                "framework_input_chars": 25600,
                "framework_input_tokens_method": "chars-div-4",
                "unique_files": 11,
                "hallucinated_paths": 0,
                "envelope_violations": 0,
            }
        ],
        "tool_events": [],
        "totals": {
            "correctness": {"passed": 12, "failed": 0},
            "gate_retries": 1,
            "context_peak_tokens": 14000,
            "framework_input_tokens_max": 6400,
            "max_unique_files": 18,
            "hallucinated_paths": 0,
            "envelope_violations": 0,
            "evidence_authentic": True,
        },
        "t7_breakdown": {"write_denied": 0, "leash_violations": 0},
        "hallucinated_breakdown": {"hallucinated": 0},
    }


def test_report_matches_schema():
    qualify.validate_document("run-report", _full_report())


def test_schema_rejects_missing_totals():
    report = _full_report()
    del report["totals"]
    with pytest.raises(qualify.SchemaValidationError, match="totals"):
        qualify.validate_document("run-report", report)
    report = _full_report()
    del report["totals"]["evidence_authentic"]
    with pytest.raises(qualify.SchemaValidationError, match="evidence_authentic"):
        qualify.validate_document("run-report", report)


def test_schema_rejects_bad_stage_shape():
    report = _full_report()
    report["stages"] = [{"stage": "intake"}]  # missing status/checks/gate_retries
    with pytest.raises(qualify.SchemaValidationError, match="validation failed"):
        qualify.validate_document("run-report", report)


def test_failure_report_with_error_is_valid():
    report = _full_report()
    report["verdict"] = "fail"
    report["stages"] = []
    report["totals"].update({
        "gate_retries": None, "context_peak_tokens": None,
        "max_unique_files": None, "hallucinated_paths": None,
        "envelope_violations": None, "evidence_authentic": False,
        "correctness": {"passed": None, "failed": None},
    })
    report["error"] = {"class": "score_error", "detail": "boom"}
    qualify.validate_document("run-report", report)
