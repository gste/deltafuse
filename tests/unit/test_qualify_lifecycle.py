"""QF-014: T2 is the EXACT lifecycle — canonical names, canonical order,
each stage completed exactly once; median correctness/process are
threshold-checked (fail-closed, NaN/boolean/missing are never passes)."""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "scripts")
sys.path.insert(0, "src")

import qualify  # noqa: E402
from deltafuse.core.lifecycle import LIFECYCLE  # noqa: E402


def _rows(stages, status="completed"):
    return [{"stage": name, "status": status, "gate_retries": 0} for name in stages]


def test_canonical_lifecycle_is_the_seven_step_contract():
    assert LIFECYCLE == (
        "intake", "analyze", "specify", "decompose", "declare", "implement", "verify",
    )


def test_exact_lifecycle_passes():
    ok, failures = qualify.check_exact_lifecycle(_rows(LIFECYCLE))
    assert ok and failures == []


def test_eight_completed_stages_fail():
    stages = list(LIFECYCLE) + ["extra"]
    ok, failures = qualify.check_exact_lifecycle(_rows(stages))
    assert not ok
    assert "unknown" in failures[0]


def test_seven_arbitrary_stages_fail():
    ok, _ = qualify.check_exact_lifecycle(
        _rows(["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta"])
    )
    assert not ok


def test_duplicate_verify_fails():
    stages = list(LIFECYCLE)
    stages[6] = "implement"
    stages = stages + ["verify"]
    ok, failures = qualify.check_exact_lifecycle(_rows(stages))
    assert not ok
    assert "duplicated" in failures[0]


def test_missing_analyze_fails():
    stages = [s for s in LIFECYCLE if s != "analyze"]
    ok, failures = qualify.check_exact_lifecycle(_rows(stages))
    assert not ok
    assert "analyze" in failures[0]


def test_reordered_stages_fail():
    stages = list(LIFECYCLE)
    stages[0], stages[1] = stages[1], stages[0]
    ok, failures = qualify.check_exact_lifecycle(_rows(stages))
    assert not ok
    assert "order" in failures[0]


@pytest.mark.parametrize("status", ["skipped", "aborted", "unknown-status", "failed"])
def test_non_completed_status_fails(status):
    rows = _rows(LIFECYCLE)
    rows[6]["status"] = status
    ok, failures = qualify.check_exact_lifecycle(rows)
    assert not ok
    assert f"verify={status}" in failures[0]


def test_single_name_mutation_changes_verdict():
    """Mutation test: replacing any lifecycle name must flip T2 to fail."""
    for index in range(len(LIFECYCLE)):
        stages = list(LIFECYCLE)
        stages[index] = f"mutated-{index}"
        ok, _ = qualify.check_exact_lifecycle(_rows(stages))
        assert not ok, f"mutation at position {index} did not flip the verdict"


def test_apply_thresholds_t2_rejects_eight_completed_stages():
    scorecard = {
        "stages": {name: {"pass": True, "checks_total": 1, "checks_passed": 1,
                          "gate_retries": 0}
                   for name in list(LIFECYCLE) + ["extra"]},
        "retries": {"check_gate": 0},
        "defense_checks": {k: {"pass": True} for k in qualify.REQUIRED_T8_CHECKS},
        "pass": True,
        "correctness": 100.0,
    }
    verdict, failures = qualify.apply_thresholds(scorecard, _clean_metrics())
    assert not verdict
    assert any(f.startswith("T2") for f in failures)


def _clean_metrics():
    return {
        "context_peak_tokens": 1000,
        "framework_input_tokens_max": 100,
        "framework_input_chars_max": 400,
        "max_unique_files": 1,
        "hallucinated_paths": 0,
        "envelope_violations": 0,
        "t7_breakdown": {},
    }


def test_apply_thresholds_t2_accepts_exact_lifecycle():
    scorecard = {
        "stages": {name: {"pass": True, "checks_total": 1, "checks_passed": 1,
                          "gate_retries": 0}
                   for name in LIFECYCLE},
        "retries": {"check_gate": 0},
        "defense_checks": {k: {"pass": True} for k in qualify.REQUIRED_T8_CHECKS},
        "pass": True,
        "correctness": 100.0,
    }
    verdict, failures = qualify.apply_thresholds(scorecard, _clean_metrics())
    assert verdict, failures


# ------------------------------------------------------------- medians


def _run(**overrides):
    run = {
        "correctness": 100.0, "process": 100.0, "gate_retries": 0,
        "context_peak_tokens": 1000, "framework_input_tokens_max": 100,
        "framework_input_chars_max": 400, "max_unique_files": 1,
        "hallucinated_paths": 0, "envelope_violations": 0,
        "evidence_authentic": True,
    }
    run.update(overrides)
    return run


def _clean_medians():
    return qualify.medians([_run(), _run(), _run()])


@pytest.mark.parametrize("value", [None, float("nan"), True, 99.9, 100.5])
def test_median_correctness_thresholds(value):
    med = _clean_medians()
    med["correctness"] = value
    ok, failures = qualify.evaluate_medians(med, [_run()])
    assert not ok
    assert any("correctness" in f for f in failures)


@pytest.mark.parametrize("value", [None, float("nan"), True, 99.9, 100.5])
def test_median_process_thresholds(value):
    med = _clean_medians()
    med["process"] = value
    ok, failures = qualify.evaluate_medians(med, [_run()])
    assert not ok
    assert any("process" in f for f in failures)


def test_median_nan_never_passes_limit_checks():
    """A NaN median must fail T4-T5 limits, not silently compare False."""
    med = _clean_medians()
    med["context_peak_tokens"] = float("nan")
    ok, failures = qualify.evaluate_medians(med, [_run()])
    assert not ok
    assert any("context_peak_tokens" in f for f in failures)


def test_process_counts_only_canonical_completed_stages():
    metrics = {
        "calls": [], "tool_events": [], "t7_breakdown": {},
        "stage_leash": [], "hallucinated_breakdown": {},
        "context_peak_tokens": None, "framework_input_tokens_max": None,
        "framework_input_chars_max": None, "max_unique_files": 0,
        "hallucinated_paths": 0, "envelope_violations": 0,
        "framework_input_tokens_method": "chars-div-4",
    }
    report = qualify._build_run_report(
        "r", "M01-cooldown", "a" * 40, "m",
        {"stages": {}, "correctness": 100.0},
        metrics, True, [],
    )
    assert report["process"] == 0.0
