"""Verification must run and pass every test the Change's records name.

cls-g31p2-m02 (2026-10-04): with tests/test_stats.py still failing, the Worker left it out
of the verification command and the converged gate closed. Over the 26 verification runs of
the bench to date the rule flags that run and one more (a Red test deleted before
verification, gemma31-335-rep) and no other.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from deltafuse.core.fsm import change_test_ids, verification_coverage_errors


def _task(change: Path, tid: str, status: str) -> None:
    (change / "tasks").mkdir(parents=True, exist_ok=True)
    (change / "tasks" / f"{tid}.md").write_text(f"---\nid: {tid}\nstatus: {status}\n---\n", encoding="utf-8")


def _record(change: Path, phase: str, name: str, **tests: list[str]) -> None:
    path = change / "evidence" / phase / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"tests": {"source": "junitxml", **tests}}), encoding="utf-8")


def _change(tmp_path: Path) -> Path:
    change = tmp_path / "CHG-001"
    _task(change, "TASK-001", "implemented")
    _record(change, "red", "TASK-001", failed=["tests.test_stats::test_counts"], passed=[])
    _record(change, "regression", "TASK-001", passed=["tests.test_limiter::test_old"])
    _task(change, "TASK-002", "superseded")
    _record(change, "red", "TASK-002", failed=[], passed=["tests.test_net::test_in_process"])
    _task(change, "TASK-003", "cancelled")
    _record(change, "red", "TASK-003", failed=["tests.test_dropped::test_x"], passed=[])
    return change


def test_the_tests_a_change_names(tmp_path):
    assert change_test_ids(_change(tmp_path)) == {
        "tests.test_stats::test_counts",
        "tests.test_limiter::test_old",
        "tests.test_net::test_in_process",
    }


def test_a_verification_that_left_a_named_test_out_is_refused(tmp_path):
    change = _change(tmp_path)
    _record(change, "verification", "run", passed=["tests.test_limiter::test_old", "tests.test_net::test_in_process"])
    errors = verification_coverage_errors(change)
    assert len(errors) == 1 and "tests.test_stats::test_counts" in errors[0]
    assert "1 of the 3 tests" in errors[0]


def test_a_full_verification_passes_and_a_cancelled_task_is_not_owed(tmp_path):
    change = _change(tmp_path)
    _record(
        change,
        "verification",
        "run",
        passed=["tests.test_stats::test_counts", "tests.test_limiter::test_old", "tests.test_net::test_in_process", "tests.test_more::test_y"],
    )
    assert verification_coverage_errors(change) == []


def test_a_verification_without_a_runner_report_is_refused(tmp_path):
    change = _change(tmp_path)
    run = change / "evidence" / "verification" / "run.yaml"
    run.parent.mkdir(parents=True, exist_ok=True)
    run.write_text("exit_code: 0\n", encoding="utf-8")
    assert "no runner report" in verification_coverage_errors(change)[0]
