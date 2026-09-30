"""What the frozen Red oracle holds beyond the test's own module (core/oracle.py).

Every conftest.py on the path from the test to the product root and every
declared Python module without tests are frozen whole (formatting aside); the
pytest configuration files on the same path by bytes. Names are not followed
into other modules. The isolated Green run keeps the Worker's options except
test selection and `-p`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
import yaml

from deltafuse.core.oracle import canon, isolation_plan
from tests.fixtures.oracle_freeze import FAILED, ORACLE, TEST_FILE, edit, errors, freeze, record_of

CONFTEST = "tests/conftest.py"
CONFTEST_TEXT = (
    "import pytest\n\n\n@pytest.fixture\ndef window():\n    return 30\n\n\n"
    "@pytest.fixture\ndef unrelated():\n    return 1\n"
)
AUTOUSE = "import pytest\n\n\n@pytest.fixture(autouse=True)\ndef _patch(monkeypatch):\n    pass\n"


# --- conftest.py on the path: frozen whole ------------------------------------

@pytest.mark.parametrize("declared", [True, False], ids=["declared", "undeclared"])
def test_a_conftest_on_the_path_is_frozen_whole_but_not_its_formatting(tmp_path: Path, declared: bool):
    files = {TEST_FILE: ORACLE, CONFTEST: CONFTEST_TEXT}
    red = freeze(tmp_path, files, FAILED, declared=list(files) if declared else [TEST_FILE])
    edit(tmp_path, "def window():", "def window():  # seconds", rel=CONFTEST)
    assert errors(tmp_path, red) == []
    edit(tmp_path, "    return 1\n", "    return 2\n", rel=CONFTEST)
    errs = errors(tmp_path, red)
    assert errs and f"{CONFTEST} changed (a conftest.py on the frozen test's path" in errs[0], errs


@pytest.mark.parametrize("where", ["tests/conftest.py", "conftest.py"])
def test_a_conftest_added_on_the_path_is_refused(tmp_path: Path, where: str):
    red = freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED)
    (tmp_path / where).write_text(AUTOUSE, encoding="utf-8")
    errs = errors(tmp_path, red)
    assert errs and f"{where} was added" in errs[0], errs


def test_a_conftest_beside_another_directory_is_not_on_the_path(tmp_path: Path):
    red = freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED)
    (tmp_path / "tests" / "other").mkdir()
    (tmp_path / "tests" / "other" / "conftest.py").write_text(AUTOUSE, encoding="utf-8")
    assert errors(tmp_path, red) == []


# --- declared helper modules: frozen whole, named ------------------------------

def test_a_declared_helper_module_that_changes_is_refused_by_name(tmp_path: Path):
    helpers = "tests/helpers.py"
    red = freeze(
        tmp_path,
        {TEST_FILE: ORACLE.replace("import sys\n", "import sys\nfrom tests.helpers import floor\n"),
         helpers: "def floor():\n    return 30\n"},
        FAILED,
    )
    edit(tmp_path, "def floor():", "def floor():  # seconds", rel=helpers)
    assert errors(tmp_path, red) == []
    edit(tmp_path, "return 30", "return 0", rel=helpers)
    errs = errors(tmp_path, red)
    assert errs and f"{helpers} changed (a declared module with no tests of its own, frozen whole)" in errs[0], errs


# --- pytest configuration on the path: by bytes --------------------------------

@pytest.mark.parametrize(
    "rel, before, after",
    [
        ("pytest.ini", "[pytest]\nmarkers = slow\n", "[pytest]\nmarkers = slow\naddopts = -p tests.cheat\n"),
        ("pyproject.toml", "[tool.pytest.ini_options]\nxfail_strict = true\n", "[tool.pytest.ini_options]\n"),
        ("tox.ini", "[pytest]\naddopts = -q\n", "[pytest]\naddopts = -q -k 'not cooldown'\n"),
        ("setup.cfg", "[tool:pytest]\n", "[tool:pytest]\npython_functions = check_*\n"),
        ("tests/pytest.ini", None, "[pytest]\naddopts = -p tests.cheat\n"),  # new, nearer the test
        ("tests/pytest.toml", None, "[pytest]\n"),
    ],
    ids=["pytest.ini", "pyproject", "tox", "setup.cfg", "nearer", "pytest.toml"],
)
def test_changing_the_pytest_configuration_on_the_path_is_refused(tmp_path: Path, rel, before, after):
    files = {TEST_FILE: ORACLE}
    if before is not None:
        files[rel] = before
    red = freeze(tmp_path, files, FAILED, declared=[TEST_FILE])
    (tmp_path / rel).write_text(after, encoding="utf-8")
    errs = errors(tmp_path, red)
    assert errs and "pytest configuration" in errs[0], errs


def test_configuration_off_the_path_is_not_frozen(tmp_path: Path):
    red = freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED)
    (tmp_path / "tests" / "other").mkdir()
    (tmp_path / "tests" / "other" / "pytest.ini").write_text("[pytest]\naddopts = -x\n", encoding="utf-8")
    assert errors(tmp_path, red) == []


# --- the AST rendering is the same across Python versions ---------------------

def test_the_ast_rendering_is_pinned():
    """`ast.dump` changed shape in 3.13 (empty fields dropped), so a digest
    taken on one Python would not match on another. The canon skips empty
    fields itself - the repository's own 145 Python files render identically
    under 3.12 and 3.14. This pins the output, so a Python that renders
    differently fails here rather than at somebody's gate."""
    tree = ast.parse(
        '@pytest.mark.skip\ndef test_a(x, *, y=1):\n    """doc"""\n    assert f(x) >= 30, "m"\n'
    )
    assert canon(tree) == (
        "Module(body=[FunctionDef(name='test_a',args=arguments(args=[arg(arg='x')],"
        "kwonlyargs=[arg(arg='y')],kw_defaults=[Constant(value=1)]),"
        "body=[Assert(test=Compare(left=Call(func=Name(id='f',ctx=Load()),"
        "args=[Name(id='x',ctx=Load())]),ops=[GtE()],comparators=[Constant(value=30)]),"
        "msg=Constant(value='m'))],decorator_list=[Attribute(value=Attribute("
        "value=Name(id='pytest',ctx=Load()),attr='mark',ctx=Load()),attr='skip',ctx=Load())])])"
    )


# --- the isolated run's command -----------------------------------------------

NODES = [
    "tests/test_limiter.py::test_cooldown",
    "tests/test_limiter.py::test_cooldown_scales",
    "tests/test_limiter.py::TestWindow::test_window",
]


def test_the_isolated_run_keeps_configuration_options_and_drops_selection_and_plugins(tmp_path: Path):
    record = record_of(freeze(tmp_path, {TEST_FILE: ORACLE, "tests/custom.ini": "[pytest]\n"}, FAILED))
    py = [sys.executable, "-m", "pytest"]
    argv = [
        *py, "-c", "tests/custom.ini", "-o", "python_functions=check_*", "--import-mode=importlib",
        "--asyncio-mode", "auto", "-q", "-p", "tests.cheat", "-pno:randomly", "-k", "cooldown",
        "--deselect=tests/test_limiter.py::test_other", "--lf", "tests", "tests/test_limiter.py::test_cooldown",
    ]
    iso, expected = isolation_plan(argv, record, FAILED, tmp_path)
    assert iso == [
        *py, "-c", "tests/custom.ini", "-o", "python_functions=check_*", "--import-mode=importlib",
        "--asyncio-mode", "auto", "-q", *NODES, "-p", "no:cacheprovider",
    ]
    assert expected == FAILED
    assert isolation_plan(["pytest.exe", "tests"], record, FAILED, tmp_path)[0] == [
        "pytest.exe", *NODES, "-p", "no:cacheprovider",
    ]


def test_there_is_no_isolated_run_for_other_runners_or_without_frozen_tests(tmp_path: Path):
    record = record_of(freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED))
    assert isolation_plan(["python", "tests/run.py"], record, FAILED, tmp_path) is None
    assert isolation_plan(["mvn", "test"], record, FAILED, tmp_path) is None
    assert isolation_plan(["pytest"], record, ["tests.test_other::test_x"], tmp_path) is None


def test_the_gate_wants_the_isolated_run_when_the_runner_reported_tests(tmp_path: Path):
    from deltafuse.core.fsm import isolation_errors

    red = freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED)
    green = tmp_path / "green.yaml"

    def gate(payload: dict) -> list[str]:
        green.write_text(yaml.safe_dump(payload), encoding="utf-8")
        return isolation_errors(red, green, "green evidence 'TASK-001.yaml'")

    reported = {"exit_code": 0, "tests": {"source": "junitxml", "passed": FAILED}}
    assert "no isolated run" in gate(reported)[0]
    assert gate({**reported, "oracle_isolation": {"command": "x", "exit_code": 0, "not_passing": []}}) == []
    errs = gate({**reported, "oracle_isolation": {"command": "x", "exit_code": 1, "not_passing": FAILED[:1]}})
    assert errs and "do not pass on their own" in errs[0], errs
    # A runner with no report cannot be narrowed, and a failed Green fails anyway.
    assert gate({"exit_code": 0}) == []
    assert gate({**reported, "exit_code": 1}) == []


# --- records --------------------------------------------------------------------

def test_a_pre_release_per_test_record_asks_for_red_again(tmp_path: Path):
    """7149cad wrote `red_oracle_tests` without `version`; it was never
    released, so its records are not checked - Red is recorded again."""
    red = freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED)
    record = yaml.safe_load(red.read_text(encoding="utf-8"))
    del record["red_oracle_tests"]["version"]
    red.write_text(yaml.safe_dump(record), encoding="utf-8")
    errs = errors(tmp_path, red)
    assert errs and "pre-release build" in errs[0] and "record Red again" in errs[0], errs


def test_a_java_file_is_frozen_whole_by_bytes(tmp_path: Path):
    """Java frozen per file, not per method; per-method is deferred until
    verified on a real Maven/Gradle run."""
    java = "src/test/java/com/acme/LimiterTest.java"
    red = freeze(tmp_path, {java: "class LimiterTest {\n  @Test void cooldown() {}\n}\n"},
                 ["com.acme.LimiterTest::cooldown()"])
    assert record_of(red)["files"] == [{"path": java, "form": "bytes", "sha256": record_of(red)["files"][0]["sha256"]}]
    assert record_of(red)["tests"] == []
    edit(tmp_path, "}\n}\n", "}\n  @Test void more() {}\n}\n", rel=java)
    errs = errors(tmp_path, red)
    assert errs and f"{java} changed" in errs[0], errs
