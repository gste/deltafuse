"""Regression and verification show that the whole suite passes.

Audit 2026-11-16 (df-evidence #4, df-gates "narrow verification"): both were judged by the exit
code and by the tests the Change's own records name. A conftest setting the session's exit status
to 0, or Maven's `-fn`, recorded "passed" over failing tests; a command narrowed to the task's own
test file converged a Change that broke an existing test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.test_reports import suite_errors, suite_subset
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder

HEADER = "import sys\nsys.path.insert(0, 'src')\nfrom calc import add, sub\n"


def _pytest(*targets: str) -> list[str]:
    return [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *targets]


def _implementing(tmp_path: Path, repo_root: Path, change_id: str) -> MockChangeBuilder:
    """Red over add, then Implement fixes add and breaks the existing sub."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id=change_id, title="Whole suite")
        .step_intake().step_analyze().step_specify()
        .step_decompose([{"id": "TASK-001", "slice": "SLICE-01", "depends_on": [],
                          "allowed_paths": ["src/calc.py", "tests/**"]}])
    )
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "calc.py").write_text(
        "def add(a, b):\n    return 0\n\n\ndef sub(a, b):\n    return a - b\n", encoding="utf-8"
    )
    (tmp_path / "tests" / "legacy").mkdir(parents=True)
    (tmp_path / "tests" / "legacy" / "test_sub.py").write_text(
        HEADER + "\ndef test_sub():\n    assert sub(3, 1) == 2\n", encoding="utf-8"
    )
    (tmp_path / "tests" / "test_add.py").write_text(
        HEADER + "\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8"
    )
    red = run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=_pytest("tests/test_add.py"),
                       changed_paths=["tests/test_add.py"])
    assert red.authentic, red.errors
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    builder._core_advance("declaring")
    (tmp_path / "src" / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a + b\n", encoding="utf-8"
    )
    green = run_evidence(builder.change_dir, phase="green", task="TASK-001", argv=_pytest("tests/test_add.py"),
                         changed_paths=["src/calc.py"])
    assert green.authentic, green.errors
    return builder


def _gate(builder: MockChangeBuilder) -> list[str]:
    set_artifact_status(builder.change_dir, status="implemented", task_id="TASK-001")
    return check_gate(builder.change_dir, "implemented")


def test_a_regression_over_part_of_the_suite_is_refused(tmp_path: Path, repo_root: Path):
    builder = _implementing(tmp_path, repo_root, "CHG-230")
    reg = run_evidence(builder.change_dir, phase="regression", task="TASK-001",
                       argv=_pytest("tests/test_add.py"), changed_paths=["src/calc.py"])
    assert not reg.authentic
    assert any("names single test files" in e for e in reg.errors), reg.errors
    assert any("names single test files" in e for e in _gate(builder))
    ver = run_evidence(builder.change_dir, phase="verification", argv=_pytest("tests/test_add.py"))
    assert not ver.authentic
    assert any("names single test files" in e for e in ver.errors), ver.errors


def test_failing_tests_are_refused_whatever_the_exit_code(tmp_path: Path, repo_root: Path):
    builder = _implementing(tmp_path, repo_root, "CHG-231")
    (tmp_path / "tests" / "legacy" / "conftest.py").write_text(
        "def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 0\n", encoding="utf-8"
    )
    reg = run_evidence(builder.change_dir, phase="regression", task="TASK-001", argv=_pytest("tests"),
                       changed_paths=["src/calc.py", "tests/legacy/conftest.py"])
    assert reg.payload["exit_code"] == 0
    assert reg.payload["tests"]["failed"] == ["tests.legacy.test_sub::test_sub"]
    assert not reg.authentic
    assert any("failed or did not run" in e for e in reg.errors), reg.errors
    assert any("failed or did not run" in e for e in _gate(builder))


def test_the_whole_suite_is_accepted(tmp_path: Path, repo_root: Path):
    builder = _implementing(tmp_path, repo_root, "CHG-232")
    (tmp_path / "src" / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n", encoding="utf-8"
    )
    reg = run_evidence(builder.change_dir, phase="regression", task="TASK-001", argv=_pytest("tests"),
                       changed_paths=["src/calc.py"])
    assert reg.authentic, reg.errors


def test_what_narrows_a_suite(tmp_path: Path):
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_a.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "test_b.py").write_text("", encoding="utf-8")
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "test_vendored.py").write_text("", encoding="utf-8")
    assert suite_subset(["pytest"], tmp_path) is None
    assert suite_subset(["python", "-m", "pytest", "-q", "tests"], tmp_path) is None
    assert suite_subset(["pytest", "tests/unit"], tmp_path)  # leaves tests/test_b.py out
    assert suite_subset(["pytest", "-k", "fast", "tests"], tmp_path)
    assert suite_subset(["pytest", "--deselect=tests/test_b.py::test_x"], tmp_path)
    assert suite_subset(["pytest", "tests/test_b.py::test_x"], tmp_path)
    assert suite_subset(["mvn", "-B", "test"], tmp_path) is None
    assert suite_subset(["mvn", "-o", "-q", "-B", "-fn", "test"], tmp_path) is None
    assert suite_subset(["mvn", "-B", "test", "-Dtest=CalcTest"], tmp_path)
    assert suite_subset(["mvn", "-B", "-pl", "core", "test"], tmp_path)
    assert suite_subset(["gradle", "test", "--tests", "demo.CalcTest"], tmp_path)
    (tmp_path / "pytest.ini").write_text("[pytest]\ntestpaths = tests/unit\n", encoding="utf-8")
    assert suite_subset(["pytest", "tests/unit"], tmp_path) is None


def test_a_declared_test_command_is_the_whole_suite(tmp_path: Path):
    (tmp_path / ".deltafuse").mkdir()
    (tmp_path / ".deltafuse" / "config.yaml").write_text(
        yaml.safe_dump({"workflow": {"test_commands": ["mvn -B test -pl service"]}}), encoding="utf-8"
    )
    assert suite_subset(["mvn", "-B", "test", "-pl", "service"], tmp_path) is None
    assert suite_subset(["mvn.cmd", "-B", "test", "-pl", "service", "-Dtest=CalcTest"], tmp_path)


def test_maven_fail_never_does_not_hide_a_failure(tmp_path: Path):
    """`mvn -fn test` exits 0 with failing tests in its reports."""
    tests = {"source": "surefire", "failed": ["demo.NegTest::negates"], "passed": ["demo.CalcTest::adds"],
             "not_run": [], "skipped": []}
    errors = suite_errors("regression", "mvn -fn test", tests, tmp_path)
    assert errors and "demo.NegTest::negates" in errors[0]
