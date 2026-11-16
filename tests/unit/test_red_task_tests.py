"""Red is about the task's own tests (q7: "the named tests executed and none passed").

Audit 2026-11-16, df-evidence: Red was judged on the whole runner report, so a test broken before
the Change made an authentic Red while the task's own test already passed (#1).
"""

from __future__ import annotations

import sys
from pathlib import Path

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder

HEADER = "import sys\nsys.path.insert(0, 'src')\nfrom calc import add\n"


def _pytest(*targets: str) -> list[str]:
    return [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *targets]


def _product(tmp_path: Path, repo_root: Path, change_id: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id=change_id, title="Red of the task")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose([{"id": "TASK-001", "slice": "SLICE-01", "depends_on": [],
                          "allowed_paths": ["src/calc.py", "tests/**"]}])
    )
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "calc.py").write_text("def add(a, b):\n    return 0\n", encoding="utf-8")
    (tmp_path / "tests").mkdir(exist_ok=True)
    return builder


def _red(builder: MockChangeBuilder, argv: list[str], paths: list[str] | None):
    return run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=argv, changed_paths=paths)


def _declaring_errors(builder: MockChangeBuilder) -> list[str]:
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    return check_gate(builder.change_dir, "declaring")


def test_a_failure_of_another_test_is_not_the_tasks_red(tmp_path: Path, repo_root: Path):
    builder = _product(tmp_path, repo_root, "CHG-220")
    (tmp_path / "tests" / "test_old.py").write_text("def test_legacy():\n    assert 1 == 2\n", encoding="utf-8")
    (tmp_path / "tests" / "test_new.py").write_text(
        HEADER + "\ndef test_add_zero():\n    assert add(0, 0) == 0\n", encoding="utf-8"
    )
    red = _red(builder, _pytest("tests"), ["tests/test_new.py"])
    assert red.payload["result"] == "expected-failure"
    assert not red.authentic
    assert red.payload["failure_category"] == "not-the-tasks-tests"
    assert any("tests.test_old::test_legacy" in e for e in red.errors), red.errors
    assert red.payload["tests"]["failed"] == []
    assert any("not-the-tasks-tests" in e for e in _declaring_errors(builder))


def test_the_tasks_failing_test_is_red_next_to_another_broken_one(tmp_path: Path, repo_root: Path):
    builder = _product(tmp_path, repo_root, "CHG-221")
    (tmp_path / "tests" / "test_old.py").write_text("def test_legacy():\n    assert 1 == 2\n", encoding="utf-8")
    (tmp_path / "tests" / "test_new.py").write_text(
        HEADER + "\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8"
    )
    red = _red(builder, _pytest("tests"), ["tests/test_new.py"])
    assert red.authentic, red.errors
    # The record's failures are the task's oracle, not the legacy test.
    assert red.payload["tests"]["failed"] == ["tests.test_new::test_add"]
    assert _declaring_errors(builder) == []


def test_a_red_that_names_no_test_is_refused(tmp_path: Path, repo_root: Path):
    builder = _product(tmp_path, repo_root, "CHG-222")
    (tmp_path / "tests" / "test_new.py").write_text(
        HEADER + "\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8"
    )
    red = _red(builder, _pytest("tests"), ["src/calc.py"])
    assert not red.authentic
    assert red.payload["failure_category"] == "tests-not-named"


def test_a_committed_test_the_command_names_is_the_tasks(tmp_path: Path, repo_root: Path):
    """No test file was written in Declare: the test the command names is the task's."""
    builder = _product(tmp_path, repo_root, "CHG-223")
    (tmp_path / "tests" / "test_old.py").write_text("def test_legacy():\n    assert 1 == 2\n", encoding="utf-8")
    (tmp_path / "tests" / "test_add.py").write_text(
        HEADER + "\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8"
    )
    red = _red(builder, _pytest("tests/test_add.py"), ["src/calc.py"])
    assert red.authentic, red.errors
    assert red.payload["tests"]["failed"] == ["tests.test_add::test_add"]
