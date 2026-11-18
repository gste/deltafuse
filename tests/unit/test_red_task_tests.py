"""Red is about the task's own tests (q7: "the named tests executed and none passed").

Audit 2026-11-16, df-evidence: Red was judged on the whole runner report, so a test broken before
the Change made an authentic Red while the task's own test already passed (#1).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.transitions import TransitionError, set_artifact_status
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
    """What stops the task at Declare: `state --status declared` (audit 3, A-13: it now refuses a
    Red the declaring gate would refuse, with the same reason), then the gate itself."""
    try:
        set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    except TransitionError as ex:
        return [str(ex), *check_gate(builder.change_dir, "declaring")]
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



# --- df-evidence #7: a Red that fails on its environment -----------------------------------------

TABLE_TEST = HEADER + '''import json, pathlib


def test_add_table():
    table = json.loads(pathlib.Path('tests/data/cases.json').read_text())
    for a, b, want in table:
        assert add(a, b) == want
'''


def test_a_missing_test_data_file_is_not_red(tmp_path: Path, repo_root: Path):
    builder = _product(tmp_path, repo_root, "CHG-224")
    (tmp_path / "tests" / "test_table.py").write_text(TABLE_TEST, encoding="utf-8")
    red = _red(builder, _pytest("tests/test_table.py"), ["tests/test_table.py"])
    assert not red.authentic
    assert red.payload["failure_category"] == "environment-error"
    assert any("tests/data/cases.json" in e for e in red.errors), red.errors
    assert any("environment-error" in e for e in _declaring_errors(builder))


def test_a_package_that_is_not_installed_is_not_red(tmp_path: Path, repo_root: Path):
    builder = _product(tmp_path, repo_root, "CHG-225")
    (tmp_path / "tests" / "test_dep.py").write_text(
        '''def test_uses_dep():
    import definitely_not_installed_pkg_xyz
    assert definitely_not_installed_pkg_xyz.ok()
''',
        encoding="utf-8",
    )
    red = _red(builder, _pytest("tests/test_dep.py"), ["tests/test_dep.py"])
    assert not red.authentic
    assert red.payload["failure_category"] == "environment-error"


def test_a_module_the_task_writes_and_a_file_the_product_reads_are_red(tmp_path: Path, repo_root: Path):
    """What the product decides stays Red: a module the task's allowed_paths will create, and a
    FileNotFoundError raised inside product code."""
    builder = _product(tmp_path, repo_root, "CHG-226")
    (tmp_path / "src" / "calc.py").write_text(
        '''def add(a, b):
    return 0


def load():
    return open('cfg/limits.ini').read()
''',
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_new.py").write_text(
        HEADER + '''

def test_new_module():
    import calc.missing_part
    assert calc.missing_part


def test_load():
    from calc import load
    assert load()
''',
        encoding="utf-8",
    )
    red = _red(builder, _pytest("tests/test_new.py"), ["tests/test_new.py"])
    assert red.authentic, red.errors
    assert red.payload["failure_category"] == "behavioral-mismatch"


# --- df-evidence #2: a Red over a committed test freezes that test --------------------------------


def test_a_committed_red_test_is_frozen(tmp_path: Path, repo_root: Path):
    """Red over a test already in git: the Core-computed changed_paths hold no test file, and the
    freeze followed changed_paths only - Implement weakened the test and Green passed."""
    from tests.fixtures.git import git

    builder = _product(tmp_path, repo_root, "CHG-227")
    test_file = tmp_path / "tests" / "test_add.py"
    test_file.write_text(HEADER + "\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    red = _red(builder, _pytest("tests/test_add.py"), None)
    assert red.authentic, red.errors
    assert "tests/test_add.py" not in red.payload["changed_paths"]
    frozen = red.payload.get("red_oracle_tests") or {}
    assert [(t["path"], t["test"]) for t in frozen.get("tests", [])] == [("tests/test_add.py", "test_add")]

    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    builder._core_advance("declaring")
    test_file.write_text(HEADER + "\ndef test_add():\n    assert add(1, 2) == 0\n", encoding="utf-8")
    green = run_evidence(builder.change_dir, phase="green", task="TASK-001", argv=_pytest("tests/test_add.py"))
    assert not green.authentic
    assert any("frozen Red oracle" in e for e in green.errors), green.errors


# --- df-evidence #10: a Red where nothing passed is not already-green -----------------------------


@pytest.mark.parametrize("marker", ["@pytest.mark.skip(reason='later')", "@pytest.mark.xfail(reason='later')"])
def test_a_skipped_or_xfailed_red_is_not_already_green(tmp_path: Path, repo_root: Path, marker: str):
    builder = _product(tmp_path, repo_root, "CHG-228")
    (tmp_path / "tests" / "test_add.py").write_text(
        "import pytest\n" + HEADER + f"\n{marker}\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8"
    )
    red = _red(builder, _pytest("tests/test_add.py"), ["tests/test_add.py"])
    assert red.payload["exit_code"] == 0
    assert red.payload["result"] != "already-green"
    assert not red.authentic
    assert any("skipped or expected to fail" in e for e in red.errors), red.errors
    assert _declaring_errors(builder)


def test_a_passing_red_test_is_still_already_green(tmp_path: Path, repo_root: Path):
    builder = _product(tmp_path, repo_root, "CHG-229")
    (tmp_path / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp_path / "tests" / "test_add.py").write_text(
        HEADER + "\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8"
    )
    red = _red(builder, _pytest("tests/test_add.py"), ["tests/test_add.py"])
    assert red.payload["result"] == "already-green"
    assert red.authentic, red.errors
