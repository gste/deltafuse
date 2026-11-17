"""A bare interpreter is no evidence on a product whose tests run under a reporting runner, and the
gates refuse what `deltafuse evidence` refused.

Audit 2026-11-16 (df-evidence #6, df-gates #2): `python tests/red_check.py` for Red and
`python tests/green_check.py` for Green and regression converged a Change with no product change
(runners.py allows a `python <file>.py`), and a `python -c` record `evidence` refused as an
unauthorized runner still satisfied the declaring and implemented gates - they re-checked result,
exit code and category, never the runner.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.runners import product_test_runner, report_less_runner_error
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder


def _product(tmp_path: Path, repo_root: Path, change_id: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=change_id, title="Runner").step_through_decompose()
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_existing.py").write_text("def test_existing():\n    assert True\n", encoding="utf-8")
    return builder


def test_a_script_runner_is_refused_on_a_pytest_product_and_at_the_gate(tmp_path: Path, repo_root: Path):
    builder = _product(tmp_path, repo_root, "CHG-240")
    (tmp_path / "tests" / "red_check.py").write_text("assert False, 'feature missing'\n", encoding="utf-8")
    red = run_evidence(builder.change_dir, phase="red", task="TASK-001",
                       argv=[sys.executable, "tests/red_check.py"], changed_paths=["tests/red_check.py"])
    assert red.payload["failure_category"] == "behavioral-mismatch"  # the log heuristic believed it
    assert not red.authentic
    assert any("bare interpreter" in e for e in red.errors), red.errors
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    assert any("bare interpreter" in e for e in check_gate(builder.change_dir, "declaring"))


def test_the_gate_refuses_an_unauthorized_runner(tmp_path: Path, repo_root: Path):
    builder = _product(tmp_path, repo_root, "CHG-241")
    red = run_evidence(builder.change_dir, phase="red", task="TASK-001",
                       argv=[sys.executable, "-c", "assert False, 'missing'"])
    assert not red.authentic
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    assert any("not an authorized runner" in e for e in check_gate(builder.change_dir, "declaring"))


def test_which_products_report_their_tests(tmp_path: Path):
    assert product_test_runner(tmp_path) == ""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_script.py").write_text("assert False\n", encoding="utf-8")
    assert product_test_runner(tmp_path) == ""  # a script named like a test is not a pytest test
    (tmp_path / "tests" / "test_real.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    assert product_test_runner(tmp_path) == "pytest"
    jvm = tmp_path / "jvm"
    jvm.mkdir()
    (jvm / "pom.xml").write_text("<project/>", encoding="utf-8")
    assert product_test_runner(jvm) == "jvm"
    assert report_less_runner_error(["python", "check.py"], route="code", product_root=jvm)
    assert report_less_runner_error(["python", "check.py"], route="docs", product_root=jvm) is None
    assert report_less_runner_error(["python", "-m", "pytest"], route="code", product_root=jvm) is None
    declared = tmp_path / "declared"
    (declared / ".deltafuse").mkdir(parents=True)
    (declared / ".deltafuse" / "config.yaml").write_text(
        yaml.safe_dump({"workflow": {"test_commands": ["python scripts/check.py"]}}), encoding="utf-8"
    )
    assert product_test_runner(declared) == ""  # the product declares a script runner itself


def test_an_interpreter_that_runs_pytest_is_refused_also_when_declared(tmp_path: Path):
    """Audit 2026-11-17, FE-3 re-probe: `python -c "...pytest.main..."` as the only entry of
    `workflow.test_commands` was a bare interpreter on a product that "declares no reporting
    runner", so Green over another test and a `--deselect` regression were accepted on the exit
    code. A command that names pytest is a way to run pytest the Core cannot read through,
    whatever its head; so is a script named after it."""
    (tmp_path / ".deltafuse").mkdir()
    (tmp_path / ".deltafuse" / "config.yaml").write_text(
        "workflow:\n  test_commands:\n    - python -c \"import sys,pytest; sys.exit(pytest.main(sys.argv[1:]))\"\n",
        encoding="utf-8",
    )
    argv = ["python", "-c", "import sys,pytest; sys.exit(pytest.main(sys.argv[1:]))", "tests/test_x.py"]
    error = report_less_runner_error(argv, route="code", product_root=tmp_path)
    assert error and "cannot read through" in error and "pytest" in error
    # the twin spelling, undeclared
    assert report_less_runner_error(["python3", "-c", "import pytest; pytest.main()"], route="code", product_root=None)
    # a script that names no runner, declared by the human, stays what it was: no report, exit code
    (tmp_path / ".deltafuse" / "config.yaml").write_text(
        "workflow:\n  test_commands:\n    - python check.py\n", encoding="utf-8")
    assert report_less_runner_error(["python", "check.py"], route="code", product_root=tmp_path) is None
    # and the readable forms are not caught by the word
    assert report_less_runner_error(["python", "-m", "pytest", "tests"], route="code", product_root=tmp_path) is None
