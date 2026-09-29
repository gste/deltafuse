"""How far the frozen Red oracle reaches beyond the test itself (core/oracle.py).

conftest.py files from the test up to the product root (declared or not,
present or not), `pytest_plugins` modules, the pytest configuration, and local
helper modules reached through imports. In each, only what the frozen tests
reach - and what pytest applies without naming it - is frozen.
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
USES_WINDOW = "\n\ndef test_window_fixture(window):\n    assert cooldown() >= window\n"
WINDOW_FAILED = [*FAILED, "tests.test_limiter::test_window_fixture"]
AUTOUSE = "import pytest\n\n\n@pytest.fixture(autouse=True)\ndef _patch(monkeypatch):\n    pass\n"


# --- conftest.py (items 1 and 4) -----------------------------------------------

@pytest.mark.parametrize("declared", [True, False], ids=["declared", "undeclared"])
def test_a_conftest_is_frozen_by_what_the_frozen_tests_reach(tmp_path: Path, declared: bool):
    files = {TEST_FILE: ORACLE + USES_WINDOW, CONFTEST: CONFTEST_TEXT}
    red = freeze(tmp_path, files, WINDOW_FAILED, declared=list(files) if declared else [TEST_FILE])
    # free: a comment, a new fixture, an unrelated fixture
    edit(tmp_path, "def window():", "def window():  # seconds", rel=CONFTEST)
    edit(
        tmp_path, "    return 1\n", "    return 2\n\n\n@pytest.fixture\ndef extra():\n    return 3\n",
        rel=CONFTEST,
    )
    assert errors(tmp_path, red) == []
    # refused: the fixture the frozen test requests, named with its file
    edit(tmp_path, "    return 30\n", "    return 0\n", rel=CONFTEST)
    errs = errors(tmp_path, red)
    assert errs and "test_window_fixture relies on changed in tests/conftest.py" in errs[0], errs


def test_an_autouse_fixture_added_to_a_declared_conftest_is_refused(tmp_path: Path):
    files = {TEST_FILE: ORACLE, CONFTEST: CONFTEST_TEXT}
    red = freeze(tmp_path, files, FAILED)
    edit(tmp_path, "import pytest\n", AUTOUSE, rel=CONFTEST)
    errs = errors(tmp_path, red)
    assert errs and "in tests/conftest.py" in errs[0], errs


@pytest.mark.parametrize(
    "where, text",
    [
        ("tests/conftest.py", AUTOUSE),
        ("conftest.py", AUTOUSE),  # at the product root, above the test directory
        ("tests/conftest.py", "import pytest\n\n\n@pytest.fixture\ndef base():\n    return 0\n"),
        ("tests/conftest.py", "def pytest_collection_modifyitems(items):\n    items.clear()\n"),
        ("tests/conftest.py", "import limiter\nlimiter.cooldown = lambda: 30\n"),
    ],
    ids=["autouse", "root-autouse", "override", "hook", "module-level"],
)
def test_a_new_undeclared_conftest_that_acts_on_the_frozen_test_is_refused(tmp_path: Path, where, text):
    red = freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED)
    (tmp_path / where).write_text(text, encoding="utf-8")
    errs = errors(tmp_path, red)
    assert errs and f"in {where}" in errs[0], errs


def test_a_new_conftest_with_unrelated_fixtures_is_not_refused(tmp_path: Path):
    red = freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED)
    (tmp_path / CONFTEST).write_text(
        "import pytest\n\n\n@pytest.fixture\ndef big():\n    return 3600\n", encoding="utf-8"
    )
    assert errors(tmp_path, red) == []


def test_a_conftest_beside_another_directory_is_not_in_scope(tmp_path: Path):
    red = freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED)
    (tmp_path / "tests" / "other").mkdir()
    (tmp_path / "tests" / "other" / "conftest.py").write_text(AUTOUSE, encoding="utf-8")
    assert errors(tmp_path, red) == []


def test_a_plugin_named_in_pytest_plugins_is_in_the_fixture_scope(tmp_path: Path):
    plugin = "tests/plugins/limits.py"
    red = freeze(
        tmp_path,
        {
            TEST_FILE: ORACLE + USES_WINDOW,
            CONFTEST: "pytest_plugins = ['tests.plugins.limits']\n",
            plugin: "import pytest\n\n\n@pytest.fixture\ndef window():\n    return 30\n",
        },
        WINDOW_FAILED,
        declared=[TEST_FILE],
    )
    edit(tmp_path, "return 30", "return 0", rel=plugin)
    errs = errors(tmp_path, red)
    assert errs and f"in {plugin}" in errs[0], errs


# --- pytest configuration (item 1) --------------------------------------------

@pytest.mark.parametrize(
    "rel, before, after",
    [
        ("pytest.ini", "[pytest]\nmarkers = slow\n", "[pytest]\nmarkers = slow\naddopts = -p tests.cheat\n"),
        (
            "pyproject.toml",
            "[tool.pytest.ini_options]\nxfail_strict = true\n",
            "[tool.pytest.ini_options]\nxfail_strict = false\n",
        ),
        ("tox.ini", "[pytest]\naddopts = -q\n", "[pytest]\naddopts = -q -k 'not cooldown'\n"),
        ("setup.cfg", "[tool:pytest]\n", "[tool:pytest]\npython_functions = check_*\n"),
        ("pytest.toml", None, "[pytest]\naddopts = ['-p', 'tests.cheat']\n"),
        ("tests/pytest.ini", None, "[pytest]\n"),  # a new config nearer the test
    ],
    ids=["pytest.ini", "pyproject", "tox", "setup.cfg", "pytest.toml", "nearer"],
)
def test_changing_the_pytest_configuration_is_refused(tmp_path: Path, rel, before, after):
    files = {TEST_FILE: ORACLE}
    if before is not None:
        files[rel] = before
    red = freeze(tmp_path, files, FAILED, declared=[TEST_FILE])
    (tmp_path / rel).write_text(after, encoding="utf-8")
    errs = errors(tmp_path, red)
    assert errs and "pytest configuration" in errs[0], errs


@pytest.mark.parametrize(
    "rel, before, after",
    [
        ("pyproject.toml", "[project]\nname = 'x'\n", "[project]\nname = 'x'\nversion = '2'\n"),
        ("setup.cfg", "[metadata]\nname = x\n", "[metadata]\nname = y\n"),
        ("pytest.ini", "[pytest]\nmarkers = slow\n", "# comment\n[pytest]\nmarkers   =   slow\n"),
        ("pyproject.toml", "[tool.pytest.ini_options]\nx = 1\n", "[tool.pytest.ini_options]\nx = 1  # same\n"),
        ("tests/other/pytest.ini", None, "[pytest]\naddopts = -x\n"),  # not on the test's path
    ],
    ids=["project", "metadata", "ini-format", "toml-comment", "elsewhere"],
)
def test_config_pytest_does_not_read_for_the_test_is_not_frozen(tmp_path: Path, rel, before, after):
    files = {TEST_FILE: ORACLE}
    if before is not None:
        files[rel] = before
    red = freeze(tmp_path, files, FAILED, declared=[TEST_FILE])
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_text(after, encoding="utf-8")
    assert errors(tmp_path, red) == []


# --- helper modules reached through imports (item 3) --------------------------

HELPERS = "tests/helpers.py"
HELPERS_TEXT = "LIMIT = 30\n\n\ndef make():\n    return LIMIT\n\n\ndef other():\n    return 1\n"


@pytest.mark.parametrize(
    "import_line, call",
    [
        ("from tests.helpers import make", "make()"),
        ("from tests import helpers", "helpers.make()"),
        ("import tests.helpers as h", "h.make()"),
        ("import tests.helpers", "tests.helpers.make()"),
        ("from .helpers import make", "make()"),
        ("from helpers import make", "make()"),  # rootdir-style: the test dir is on sys.path
        ("from tests.helpers import *", "make()"),
    ],
)
def test_a_helper_the_frozen_test_uses_through_an_import_is_frozen(tmp_path: Path, import_line, call):
    test = f"import pytest\n{import_line}\n\n\ndef test_uses_helper():\n    assert {call} >= 30\n"
    red = freeze(
        tmp_path,
        {"tests/__init__.py": "", TEST_FILE: test, HELPERS: HELPERS_TEXT},
        ["tests.test_limiter::test_uses_helper"],
        declared=[TEST_FILE],
    )
    # an unrelated helper in the same module is free
    edit(tmp_path, "    return 1\n", "    return 2\n", rel=HELPERS)
    assert errors(tmp_path, red) == []
    # what the helper the test calls refers to is not - transitively
    edit(tmp_path, "LIMIT = 30", "LIMIT = 0", rel=HELPERS)
    errs = errors(tmp_path, red)
    assert errs and f"in {HELPERS}" in errs[0], errs


def test_product_code_imported_by_the_test_is_not_frozen(tmp_path: Path):
    red = freeze(
        tmp_path, {TEST_FILE: ORACLE, "limiter.py": "def cooldown():\n    return 0\n"}, FAILED,
        declared=[TEST_FILE],
    )
    edit(tmp_path, "return 0", "return 30", rel="limiter.py")
    assert errors(tmp_path, red) == []


# --- the AST rendering is the same across Python versions (item 5) ------------

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


def test_a_refusal_names_the_python_the_record_was_taken_under(tmp_path: Path):
    red = freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED)
    record = yaml.safe_load(red.read_text(encoding="utf-8"))
    assert record["red_oracle_tests"]["python"] == f"{sys.version_info.major}.{sys.version_info.minor}"
    record["red_oracle_tests"]["python"] = "3.9"
    red.write_text(yaml.safe_dump(record), encoding="utf-8")
    edit(tmp_path, "assert cooldown() >= base", "assert cooldown() >= 0")
    errs = errors(tmp_path, red)
    assert errs and "recorded under Python 3.9" in errs[0], errs


# --- the isolated run's command (item 2) --------------------------------------

def test_the_isolated_run_selects_the_frozen_tests_and_drops_the_workers_options(tmp_path: Path):
    record = record_of(freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED))
    argv = [sys.executable, "-m", "pytest", "-p", "tests.cheat", "-o", "x=1", "-c", "other.ini", "tests"]
    iso, expected = isolation_plan(argv, record, FAILED)
    assert iso == [
        sys.executable, "-m", "pytest",
        "tests/test_limiter.py::test_cooldown",
        "tests/test_limiter.py::test_cooldown_scales",
        "tests/test_limiter.py::TestWindow::test_window",
        "-p", "no:cacheprovider",
    ]
    assert expected == FAILED
    assert isolation_plan(["pytest.exe", "-q"], record, FAILED)[0][0] == "pytest.exe"
    assert isolation_plan(["python", "tests/run.py"], record, FAILED) is None
    assert isolation_plan(argv, record, ["tests.test_other::test_x"]) is None


# --- records written before format 2 ------------------------------------------

def test_a_format_1_record_is_checked_as_it_was_taken(tmp_path: Path):
    """7149cad wrote `red_oracle_tests` without `version`: declared files only,
    support modules frozen whole. Such a record is checked by that logic."""
    from deltafuse.core import oracle_v1

    files = {TEST_FILE: ORACLE, CONFTEST: CONFTEST_TEXT}
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    units = oracle_v1._units(oracle_v1._parse(tmp_path / TEST_FILE).body)
    body, context, refs = oracle_v1._locate(units, ["test_cooldown"])
    record = {
        "tests": [{
            "path": TEST_FILE,
            "test": "test_cooldown",
            "body": oracle_v1._sha("\n".join(body)),
            "context": oracle_v1._context_digest({TEST_FILE: units}, context, refs),
        }],
        "files": [{"path": CONFTEST, "form": "ast", "sha256": oracle_v1._file_digest(tmp_path, CONFTEST, "ast")}],
    }
    red_file = tmp_path / "red.yaml"
    red_file.write_text(
        yaml.safe_dump({"changed_paths": list(files), "red_oracle_tests": record}), encoding="utf-8"
    )
    assert errors(tmp_path, red_file) == []
    # Format 1 froze a declared conftest whole, so an unrelated fixture counts.
    edit(tmp_path, "    return 1\n", "    return 2\n", rel=CONFTEST)
    assert any(f"{CONFTEST} changed" in e for e in errors(tmp_path, red_file))


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
