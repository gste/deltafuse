"""A task's Red is about that task's tests - not about every test in the dirty tree.

Audit 2026-11-17 (FE-1): Declare runs for every task before Implement, so TASK-001's Red test is
still failing and still uncommitted when TASK-002 takes its Red. The Core computed the changed
paths as the whole dirty set and read both test files as TASK-002's: its Red was authentic on
TASK-001's failing test while its own test already passed, and `implemented` closed with no delta.
A test another task's Red recorded as failing is that task's test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core import test_reports as reports
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.evidence_kit import git_init, only, product, pytest_argv, write

HEAD = "import sys\nsys.path.insert(0, 'src')\nimport limiter\n\n\n"
COOLDOWN = "def test_cooldown():\n    assert limiter.cooldown() >= 30\n"
BURST = "def test_burst():\n    assert limiter.burst() == 5\n"
ALLOWED = ["src/limiter.py", "tests/test_cooldown.py", "tests/test_burst.py", "tests/test_shared.py"]


def _two_tasks(tmp_path: Path, repo_root: Path):
    builder = product(tmp_path, repo_root, tasks=("TASK-001", "TASK-002"), allowed=ALLOWED)
    write(tmp_path / "src/limiter.py", "def cooldown():\n    return 0\n\n\ndef burst():\n    return 5\n")
    (tmp_path / "tests").mkdir(exist_ok=True)
    git_init(tmp_path)
    return builder


def _red(builder, task: str, *targets: str):
    return run_evidence(builder.change_dir, phase="red", task=task, argv=pytest_argv(*targets))


@pytest.mark.parametrize("targets", [("tests",), (), ("tests/test_cooldown.py", "tests/test_burst.py")])
def test_a_siblings_failing_test_is_not_this_tasks_red(tmp_path: Path, repo_root: Path, targets):
    builder = _two_tasks(tmp_path, repo_root)
    write(tmp_path / "tests/test_cooldown.py", HEAD + COOLDOWN)
    red1 = _red(builder, "TASK-001", "tests/test_cooldown.py")
    assert red1.authentic, red1.errors
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")

    write(tmp_path / "tests/test_burst.py", HEAD + BURST)  # the behaviour is already there
    red2 = _red(builder, "TASK-002", *targets)
    assert not red2.authentic
    assert red2.payload["failure_category"] == "not-the-tasks-tests"
    assert red2.payload["tests"]["failed"] == []
    assert "red_oracle_tests" not in red2.payload
    assert only(red2.errors, "TASK-001's Red"), red2.errors
    # ... and so the chain that closed `implemented` with no delta stops at Declare.
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-002")
    assert only(check_gate(builder.change_dir, "declaring"), "not-the-tasks-tests")


def test_a_siblings_test_in_the_same_file_is_not_this_tasks_red(tmp_path: Path, repo_root: Path):
    """The bypass through one shared test file, named on the command line."""
    builder = _two_tasks(tmp_path, repo_root)
    write(tmp_path / "tests/test_shared.py", HEAD + COOLDOWN)
    assert _red(builder, "TASK-001", "tests/test_shared.py").authentic
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    write(tmp_path / "tests/test_shared.py", HEAD + COOLDOWN + "\n\n" + BURST)
    red2 = _red(builder, "TASK-002", "tests/test_shared.py")
    assert not red2.authentic
    assert red2.payload["failure_category"] == "not-the-tasks-tests"


def test_the_tasks_own_failing_test_is_red_beside_a_siblings(tmp_path: Path, repo_root: Path):
    builder = _two_tasks(tmp_path, repo_root)
    write(tmp_path / "tests/test_cooldown.py", HEAD + COOLDOWN)
    assert _red(builder, "TASK-001", "tests/test_cooldown.py").authentic
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    write(tmp_path / "tests/test_burst.py", HEAD + "def test_burst():\n    assert limiter.burst() == 9\n")
    red2 = _red(builder, "TASK-002", "tests")
    assert red2.authentic, red2.errors
    assert red2.payload["tests"]["failed"] == ["tests.test_burst::test_burst"]
    # A task may take its own Red again while the Change is in Declare: its record is not a sibling's.
    again = _red(builder, "TASK-001", "tests")
    assert again.authentic, again.errors
    assert again.payload["tests"]["failed"] == ["tests.test_cooldown::test_cooldown"]


def test_a_red_taken_in_the_wrong_order_stops_at_the_other_task_and_has_a_way_out(tmp_path: Path, repo_root: Path):
    """Both test files written first, TASK-002's Red taken over the whole suite: the Core cannot
    know yet that the failing test is TASK-001's. It finds out when TASK-001 records its Red, says
    which record holds the test, and the retake it names frees it."""
    builder = _two_tasks(tmp_path, repo_root)
    write(tmp_path / "tests/test_cooldown.py", HEAD + COOLDOWN)
    write(tmp_path / "tests/test_burst.py", HEAD + BURST)
    wrong = _red(builder, "TASK-002", "tests")
    assert wrong.payload["tests"]["failed"] == ["tests.test_cooldown::test_cooldown"]
    red1 = _red(builder, "TASK-001", "tests/test_cooldown.py")
    assert not red1.authentic
    message = "\n".join(red1.errors)
    assert "TASK-002's Red" in message and "--phase red --task TASK-002" in message, red1.errors
    retake = _red(builder, "TASK-002", "tests/test_burst.py")
    assert retake.payload["result"] == "already-green"
    assert _red(builder, "TASK-001", "tests/test_cooldown.py").authentic


def test_a_cancelled_siblings_red_holds_no_test(tmp_path: Path, repo_root: Path):
    builder = _two_tasks(tmp_path, repo_root)
    write(tmp_path / "tests/test_cooldown.py", HEAD + COOLDOWN)
    assert _red(builder, "TASK-001", "tests/test_cooldown.py").authentic
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(task.read_text(encoding="utf-8").replace("status: pending", "status: cancelled"), encoding="utf-8")
    assert _red(builder, "TASK-002", "tests/test_cooldown.py").authentic


def test_the_jvm_reading_leaves_a_siblings_tests_out_too(tmp_path: Path):
    """The twin path: a Surefire report and a `-Dtest=` pattern that matches both classes."""
    report = reports.TestReport("surefire", {"demo.CooldownTest::waits": "failed", "demo.BurstTest::allows": "passed"})
    argv = ["mvn", "test", "-Dtest=*Test"]
    ids, _ = reports.task_test_ids(report, [], argv, tmp_path)
    assert ids == ["demo.BurstTest::allows", "demo.CooldownTest::waits"]
    ids, _ = reports.task_test_ids(report, [], argv, tmp_path, taken={"demo.CooldownTest::waits": "TASK-001"})
    assert ids == ["demo.BurstTest::allows"]
