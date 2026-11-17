"""One reading of a test command, however the runner is spelled.

Audit 2026-11-17: `workflow.test_commands: ["python -X utf8 -m pytest"]` made the command a runner
the Core had no reader for, so no report was read at all - a Green over another test and a
regression that deselected the Red test were accepted (FE-3). `python3 -m pytest` and
`py -m pytest` were refused as unauthorized (FE-12); an entry with a quoted argument never matched
(FE-13); and `./gradlew test`, the form `fuseback runner` writes, never authorized any command
(FP-6).
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.oracle import isolation_plan
from deltafuse.core.runners import product_test_runner, report_less_runner_error, runner_is_authorized
from deltafuse.core.test_reports import (
    pytest_args_start,
    pytest_positionals,
    runner_family,
    suite_subset,
    wants_junit_flag,
)
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.evidence_kit import product, write

LIMITER_TESTS = (
    "import sys\nsys.path.insert(0, 'src')\nfrom limiter import cooldown\n\n\n"
    "def test_cooldown():\n    assert cooldown() >= 30\n\n\n"
    "def test_unrelated():\n    assert True\n"
)


def _config(root: Path, *commands: str) -> None:
    lines = "".join(f"    - {c}\n" for c in commands)
    write(root / ".deltafuse/config.yaml", "workflow:\n  test_commands:\n" + lines)


# --- FE-3: a wrapper around pytest is still pytest --------------------------------------------------

@pytest.mark.parametrize("argv,start", [
    (["pytest", "-q"], 1),
    ([".venv/Scripts/pytest.exe"], 1),
    (["python", "-m", "pytest", "tests"], 3),
    (["python", "-X", "utf8", "-m", "pytest", "tests"], 5),
    (["python", "-Xutf8", "-W", "error", "-B", "-m", "pytest"], 7),
    (["python3.12", "-m", "pytest"], 3),
    (["py", "-3.12", "-m", "pytest"], 4),
    (["uv", "run", "pytest", "-q"], 3),
    (["uv", "run", "--frozen", "--with", "pytest-xdist", "pytest"], 6),
    (["uv", "run", "python", "-m", "pytest"], 5),
    (["poetry", "run", "pytest"], 3),
    (["poetry", "run", "python", "-X", "utf8", "-m", "pytest"], 7),
    (["pipenv", "run", "pytest"], 3),
    (["hatch", "run", "pytest"], 3),
    (["pdm", "run", "pytest"], 3),
])
def test_where_pytests_own_arguments_begin(argv: list[str], start: int):
    assert pytest_args_start(argv) == start
    assert runner_family(argv) == "pytest"
    assert wants_junit_flag(argv)


@pytest.mark.parametrize("argv", [
    ["python", "tests/check.py"], ["python", "-c", "import pytest"], ["python", "-m", "tox"],
    ["uv", "sync"], ["poetry", "install"], ["uv", "run", "ruff", "check"], ["make", "test"], [],
])
def test_what_is_not_a_pytest_command(argv: list[str]):
    assert pytest_args_start(argv) is None
    assert runner_family(argv) == ""


def test_the_wrappers_own_arguments_are_not_test_paths(tmp_path: Path):
    write(tmp_path / "tests/test_a.py", "def test_a():\n    assert True\n")
    write(tmp_path / "utf8", "")  # a file named like the value of `-X`
    argv = ["python", "-X", "utf8", "-m", "pytest", "tests/test_a.py::test_a"]
    assert pytest_positionals(argv, tmp_path) == ["tests/test_a.py::test_a"]
    frozen = {"version": 2, "tests": [{"path": "tests/test_a.py", "test": "test_a", "body": "", "context": ""}]}
    plan = isolation_plan(["uv", "run", "pytest", "-k", "a", "tests"], frozen, ["tests.test_a::test_a"], tmp_path)
    assert plan is not None
    assert plan[0] == ["uv", "run", "pytest", "tests/test_a.py::test_a", "-p", "no:cacheprovider"]


def test_a_declared_wrapper_still_links_green_to_red(tmp_path: Path, repo_root: Path):
    """The reproduction: no product change, Green over another test, a regression without the Red test."""
    builder = product(tmp_path, repo_root, allowed=["src/limiter.py", "tests/test_limiter.py"],
                      workflow={"test_commands": ["python -X utf8 -m pytest"]})
    write(tmp_path / "src/limiter.py", "def cooldown():\n    return 0\n")
    write(tmp_path / "tests/test_limiter.py", LIMITER_TESTS)
    wrapper = [sys.executable, "-X", "utf8", "-m", "pytest", "-p", "no:cacheprovider"]
    paths = ["tests/test_limiter.py"]
    red = run_evidence(builder.change_dir, phase="red", task="TASK-001",
                       argv=[*wrapper, "tests/test_limiter.py::test_cooldown"], changed_paths=paths)
    assert red.authentic, red.errors
    assert red.payload["tests"]["failed"] == ["tests.test_limiter::test_cooldown"]  # the report was read
    assert red.payload["red_oracle_tests"]["tests"]
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    builder._core_advance("declaring")
    green = run_evidence(builder.change_dir, phase="green", task="TASK-001",
                         argv=[*wrapper, "tests/test_limiter.py::test_unrelated"], changed_paths=paths)
    assert not green.authentic
    leave_out = [*wrapper, "--deselect", "tests/test_limiter.py::test_cooldown"]
    reg = run_evidence(builder.change_dir, phase="regression", task="TASK-001", argv=leave_out, changed_paths=paths)
    ver = run_evidence(builder.change_dir, phase="verification", argv=leave_out, changed_paths=paths)
    assert not reg.authentic and not ver.authentic
    assert any("selects part of the suite" in e or "--deselect" in e for e in reg.errors), reg.errors
    set_artifact_status(builder.change_dir, status="implemented", task_id="TASK-001")
    assert check_gate(builder.change_dir, "implemented")


def test_a_declared_wrapper_makes_the_product_a_pytest_product(tmp_path: Path):
    _config(tmp_path, "python -X utf8 -m pytest")
    assert product_test_runner(tmp_path) == "pytest"
    _config(tmp_path, "uv run pytest")
    assert product_test_runner(tmp_path) == "pytest"
    _config(tmp_path, "./gradlew test")
    assert product_test_runner(tmp_path) == "jvm"


@pytest.mark.parametrize("argv", [
    ["pipx", "run", "pytest", "tests"], ["nox", "-s", "tests", "--", "pytest"], ["cmd", "/c", "pytest"],
    ["bash", "-c", "pytest tests"], ["coverage", "run", "-m", "pytest"], ["xvfb-run", "mvn", "test"],
])
def test_a_wrapper_the_core_cannot_read_through_is_refused_not_accepted_blind(tmp_path: Path, argv: list[str]):
    """The bypass: any other wrapper declared in `test_commands` turned report reading off again."""
    _config(tmp_path, shlex.join(argv))
    assert runner_is_authorized(argv, route="code", product_root=tmp_path)  # the product declared it
    why = report_less_runner_error(argv, route="code", product_root=tmp_path)
    assert why and "cannot read" in why, why
    assert report_less_runner_error(["npm", "test"], route="code", product_root=tmp_path) is None


def test_the_gate_refuses_a_record_taken_through_an_unread_wrapper(tmp_path: Path, repo_root: Path, monkeypatch):
    builder = product(tmp_path, repo_root, allowed=["src/limiter.py", "tests/test_limiter.py"],
                      workflow={"test_commands": ["pipx run pytest"]})
    write(tmp_path / "tests/test_limiter.py", "def test_x():\n    assert 1 == 2\n")
    from deltafuse.core import evidence

    monkeypatch.setattr(evidence, "_launch", lambda argv, **kw: (1, b"assert 1 == 2\nAssertionError", b"", False))
    red = evidence.run_evidence(builder.change_dir, phase="red", task="TASK-001",
                                argv=["pipx", "run", "pytest", "tests/test_limiter.py"],
                                changed_paths=["tests/test_limiter.py"])
    assert not red.authentic
    assert any("cannot read" in e for e in red.errors), red.errors
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    assert any("cannot read" in e for e in check_gate(builder.change_dir, "declaring"))


# --- FE-12: ordinary spellings of the interpreter ---------------------------------------------------

@pytest.mark.parametrize("argv", [
    ["python3", "-m", "pytest"], ["python3", "-m", "pytest", "-q"], ["py", "-m", "pytest"],
    ["python3.12", "-m", "pytest"], ["py", "-3", "-m", "pytest", "tests"], ["mvn.cmd", "-B", "test"],
    ["./mvnw", "test"], ["uv", "run", "pytest"], ["poetry", "run", "pytest", "-q"],
    ["./gradlew", "test"], ["gradlew.bat", "check"],
])
def test_the_default_allowlist_accepts_ordinary_runner_spellings(tmp_path: Path, argv: list[str]):
    assert runner_is_authorized(argv, route="code", product_root=tmp_path)


@pytest.mark.parametrize("argv", [
    ["python3", "-c", "print('green')"], ["py", "-c", "print('green')"], ["python3.12", "-m", "http.server"],
    ["uv", "run", "python", "-c", "pass"], ["poetry", "run", "echo", "ok"], ["./gradlew", "publish"],
])
def test_the_default_allowlist_still_refuses_what_runs_no_test(tmp_path: Path, argv: list[str]):
    assert not runner_is_authorized(argv, route="code", product_root=tmp_path)


def test_a_declared_python_command_matches_another_spelling_of_the_interpreter(tmp_path: Path):
    _config(tmp_path, "python -m pytest")
    for head in ("python3", "py", "python3.12", sys.executable):
        assert runner_is_authorized([head, "-m", "pytest", "-q"], route="code", product_root=tmp_path)
    assert not runner_is_authorized(["python3", "-m", "tox"], route="code", product_root=tmp_path)


# --- FE-13: a declared command with a quoted argument -----------------------------------------------

def test_a_declared_command_with_a_quoted_argument_is_usable(tmp_path: Path):
    _config(tmp_path, 'pytest -m "not slow"')
    argv = ["pytest", "-m", "not slow"]
    assert runner_is_authorized(argv, route="code", product_root=tmp_path)
    assert suite_subset(argv, tmp_path) is None  # the suite as declared
    assert suite_subset([*argv, "-k", "x"], tmp_path) is not None
    assert not runner_is_authorized(["pytest", "-m", "not", "slow"], route="code", product_root=tmp_path)


def test_a_declared_command_with_a_windows_path_and_single_quotes(tmp_path: Path):
    write(tmp_path / ".deltafuse/config.yaml",
          "workflow:\n  test_commands:\n    - .venv\\Scripts\\pytest.exe -m 'not slow' -q\n")
    assert runner_is_authorized([".venv/Scripts/pytest.exe", "-m", "not slow", "-q"], route="code", product_root=tmp_path)
    assert runner_is_authorized(["pytest", "-m", "not slow", "-q", "tests"], route="code", product_root=tmp_path)


# --- FP-6: the wrapper forms of Gradle and Maven ----------------------------------------------------

@pytest.mark.parametrize("declared", ["./gradlew test", "gradlew test", "gradlew.bat test", ".\\gradlew.bat test"])
@pytest.mark.parametrize("argv", [
    ["./gradlew", "test"], ["gradlew", "test", "--rerun"], ["gradlew.bat", "test"],
    ["./gradlew", "test", "--tests", "demo.CalcTest"],
])
def test_a_declared_gradle_wrapper_authorizes_its_forms(tmp_path: Path, declared: str, argv: list[str]):
    _config(tmp_path, declared)
    assert runner_is_authorized(argv, route="code", product_root=tmp_path)
    assert not runner_is_authorized(["./gradlew", "publish"], route="code", product_root=tmp_path)
    assert not runner_is_authorized(["gradle", "test"], route="code", product_root=tmp_path)  # another program


def test_a_declared_maven_wrapper_authorizes_its_forms(tmp_path: Path):
    _config(tmp_path, "./mvnw -B test")
    for head in ("./mvnw", "mvnw", "mvnw.cmd"):
        assert runner_is_authorized([head, "-B", "test", "-Dtest=CalcTest"], route="code", product_root=tmp_path)
    assert suite_subset(["mvnw.cmd", "-B", "test"], tmp_path) is None


def test_a_declared_pytest_authorizes_other_ways_of_starting_pytest(tmp_path: Path):
    _config(tmp_path, "python -m pytest -q")
    for argv in (["pytest", "-q", "tests"], [sys.executable, "-X", "utf8", "-m", "pytest", "-q"],
                 ["uv", "run", "pytest", "-q"]):
        assert runner_is_authorized(argv, route="code", product_root=tmp_path), argv
    assert not runner_is_authorized(["pytest", "tests"], route="code", product_root=tmp_path)  # not the declared `-q`
