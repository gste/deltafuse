"""A passing run that ran no test is not evidence.

Fuse-Back, Gradle J01 (2026-10-09): right after Green, regression ran the same `gradle test`;
Gradle reported the test task UP-TO-DATE and ran nothing, and the record read `exit_code: 0`,
`passed`, authentic. Only the converged gate noticed, and only for the verification run.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import validate_change_package
from deltafuse.core.installer import install
from deltafuse.core.test_reports import no_test_ran
from tests.fixtures.change_builder import MockChangeBuilder

UP_TO_DATE_LOG = "> Task :compileJava UP-TO-DATE\n> Task :test UP-TO-DATE\n\nBUILD SUCCESSFUL in 1s\n3 actionable tasks: 3 up-to-date"


def test_a_gradle_test_task_up_to_date_names_rerun():
    why = no_test_ran("gradle --no-daemon test", None, UP_TO_DATE_LOG)
    assert why and "up to date" in why and "--rerun" in why
    # Gradle's summary line alone, as a run without --console=plain prints it
    assert "--rerun" in (no_test_ran(["./gradlew", "test"], None, "BUILD SUCCESSFUL\n2 actionable tasks: 2 up-to-date") or "")


def test_a_reporting_runner_without_a_report_or_with_an_empty_one_ran_no_test():
    assert "left no test report" in (no_test_ran(["mvn", "-B", "test"], None, "BUILD SUCCESS") or "")
    assert "names none" in (no_test_ran("python -m pytest tests", {"source": "junitxml", "passed": []}) or "")
    assert "names none" in (no_test_ran("pytest", {"source": "junitxml", "skipped": ["a::b"]}) or "")


def test_a_run_that_ran_tests_or_a_runner_the_core_cannot_read_is_not_judged():
    assert no_test_ran("gradle test", {"source": "surefire", "passed": ["a::b"]}, UP_TO_DATE_LOG) is None
    assert no_test_ran("pytest", {"source": "junitxml", "failed": ["a::b"]}) is None
    assert no_test_ran("npm test", None) is None
    assert no_test_ran(None, None) is None


def _builder(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return (
        MockChangeBuilder(tmp_path, change_id="CHG-090", title="Regression without tests")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )


def _fake_gradle(tmp_path: Path) -> str:
    """A `gradlew` that does what Gradle does when nothing changed: run nothing, exit 0."""
    if os.name == "nt":
        script = tmp_path / "gradlew.bat"
        script.write_text("@echo off\r\necho ^> Task :test UP-TO-DATE\r\necho BUILD SUCCESSFUL\r\n", encoding="utf-8")
    else:
        script = tmp_path / "gradlew"
        script.write_text("#!/bin/sh\necho '> Task :test UP-TO-DATE'\necho 'BUILD SUCCESSFUL'\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_an_up_to_date_gradle_regression_is_refused_when_recorded_and_by_the_gate(tmp_path: Path, repo_root: Path):
    builder = _builder(tmp_path, repo_root)
    # A report Green left behind is older than this run and does not count.
    old = tmp_path / "build" / "test-results" / "test" / "TEST-a.Old.xml"
    old.parent.mkdir(parents=True)
    old.write_text('<testsuite><testcase classname="a.Old" name="t"/></testsuite>', encoding="utf-8")
    os.utime(old, (1, 1))

    outcome = run_evidence(
        builder.change_dir, phase="regression", task="TASK-001", argv=[_fake_gradle(tmp_path), "test"]
    )
    assert outcome.payload["exit_code"] == 0 and outcome.payload["result"] == "passed"
    assert "tests" not in outcome.payload
    assert not outcome.authentic
    assert any("regression is not evidence" in e and "--rerun" in e for e in outcome.errors), outcome.errors

    errors = validate_change_package(builder.change_dir)
    assert any("regression/TASK-001.yaml" in e.replace("\\", "/") and "--rerun" in e for e in errors), errors


def test_a_pytest_regression_with_the_workers_own_report_path_is_read(tmp_path: Path, repo_root: Path):
    builder = _builder(tmp_path, repo_root)
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_old.py").write_text("def test_old():\n    assert True\n", encoding="utf-8")
    outcome = run_evidence(
        builder.change_dir,
        phase="regression",
        task="TASK-001",
        argv=[sys.executable, "-m", "pytest", "tests/test_old.py", "--junitxml", "out/report.xml"],
    )
    assert outcome.payload["tests"]["passed"], outcome.payload
    assert not any("not evidence" in e for e in outcome.errors), outcome.errors
