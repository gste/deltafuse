"""The Red oracle frozen per failed test (core/oracle.py, `red_oracle_tests`).

Each case freezes a small test tree as Red would, edits it as Implement might,
and asks the check the Green evidence call and the implemented gate both use.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.core.hasher import compute_red_oracle_digest
from tests.fixtures.oracle_freeze import FAILED, ORACLE, TEST_FILE
from tests.fixtures.oracle_freeze import edit as _edit
from tests.fixtures.oracle_freeze import errors as _errors
from tests.fixtures.oracle_freeze import freeze as _freeze


@pytest.fixture
def frozen(tmp_path: Path) -> Path:
    return _freeze(tmp_path, {TEST_FILE: ORACLE}, FAILED)


def test_the_record_names_each_failed_test_once(tmp_path: Path, frozen: Path):
    record = yaml.safe_load(frozen.read_text(encoding="utf-8"))["red_oracle_tests"]
    assert sorted(t["test"] for t in record["tests"]) == [
        "TestWindow::test_window", "test_cooldown", "test_cooldown_scales",
    ]
    # Only the conftest.py files on the test's path, absent here.
    assert record["files"] == [
        {"path": "conftest.py", "form": "ast", "sha256": None},
        {"path": "tests/conftest.py", "form": "ast", "sha256": None},
    ]
    assert _errors(tmp_path, frozen) == []


# --- what must still be refused -------------------------------------------------

@pytest.mark.parametrize(
    "old, new, named",
    [
        ("assert cooldown() >= base", "assert cooldown() >= 0", "test_cooldown changed"),
        ("assert cooldown() * n >= 30 * n", "assert cooldown() * n >= 0", "test_cooldown_scales changed"),
        ("[1, 2]", "[0]", "test_cooldown_scales changed"),
        ("def test_cooldown(base):", "@pytest.mark.xfail\ndef test_cooldown(base):", "test_cooldown changed"),
        ("def test_cooldown(base):", "@pytest.mark.skip\ndef test_cooldown(base):", "test_cooldown changed"),
        ('@pytest.mark.parametrize("n", [1, 2])\n', "", "test_cooldown_scales changed"),
        ("def test_cooldown(base):", "def test_cooldown_old(base):", "test_cooldown was removed or renamed"),
        ("assert cooldown() >= self.limit", "assert True", "TestWindow::test_window changed"),
    ],
)
def test_editing_a_frozen_test_is_refused_and_named(tmp_path: Path, frozen: Path, old, new, named):
    _edit(tmp_path, old, new)
    errs = _errors(tmp_path, frozen)
    assert len(errs) == 1 and "frozen Red oracle" in errs[0], errs
    assert f"{TEST_FILE}::{named}" in errs[0], errs[0]
    assert "record Red again" in errs[0]


def test_removing_a_skip_the_red_test_carried_is_refused(tmp_path: Path):
    oracle = ORACLE.replace(
        "def test_cooldown(base):", '@pytest.mark.skipif(sys.platform == "x", reason="x")\ndef test_cooldown(base):'
    )
    red = _freeze(tmp_path, {TEST_FILE: oracle}, FAILED)
    _edit(tmp_path, '@pytest.mark.skipif(sys.platform == "x", reason="x")\n', "")
    assert any("test_cooldown changed" in e for e in _errors(tmp_path, red))


def test_deleting_a_frozen_test_is_refused(tmp_path: Path, frozen: Path):
    _edit(tmp_path, 'def test_cooldown(base):\n    """Cooldown is at least the base."""\n    assert cooldown() >= base\n', "")
    assert any("test_cooldown was removed or renamed" in e for e in _errors(tmp_path, frozen))


def test_redefining_a_frozen_test_further_down_is_refused(tmp_path: Path, frozen: Path):
    (tmp_path / TEST_FILE).write_text(ORACLE + "\n\ndef test_cooldown():\n    pass\n", encoding="utf-8")
    assert any("test_cooldown changed" in e for e in _errors(tmp_path, frozen))


def test_deleting_the_test_file_is_refused(tmp_path: Path, frozen: Path):
    (tmp_path / TEST_FILE).unlink()
    errs = _errors(tmp_path, frozen)
    assert len(errs) == 1 and f"{TEST_FILE} was deleted" in errs[0], errs


@pytest.mark.parametrize(
    "old, new",
    [
        ("    return 30\n", "    return 0\n"),  # the fixture the test requests
        ("from limiter import cooldown", "from fake_limiter import cooldown"),  # the name it calls
        ("import sys\n", "import sys\npytestmark = pytest.mark.skip\n"),  # applies without a name
        ("import sys\n", "import sys\nsys.modules['limiter'] = None\n"),  # module-level code
        ("class TestWindow:\n    limit = 30", "class TestWindow:\n    limit = 0"),  # class attribute
        ("class TestWindow:", "@pytest.mark.skip\nclass TestWindow:"),  # class decorator
        (  # a fixture overriding the one the test requests
            "def helper():",
            "@pytest.fixture(name='base')\ndef _cheap():\n    return 0\n\n\ndef helper():",
        ),
        (  # an autouse fixture
            "def helper():",
            "@pytest.fixture(autouse=True)\ndef _patch(monkeypatch):\n    pass\n\n\ndef helper():",
        ),
    ],
)
def test_changing_what_a_frozen_test_relies_on_is_refused(tmp_path: Path, frozen: Path, old, new):
    _edit(tmp_path, old, new)
    errs = _errors(tmp_path, frozen)
    assert errs and "relies on changed" in errs[0], errs


# --- what must not be refused --------------------------------------------------

@pytest.mark.parametrize(
    "old, new",
    [
        # comments, blank lines, formatting, docstrings
        ("def test_cooldown(base):", "# the base is the product's floor\ndef test_cooldown(base):  # noqa"),
        ("    assert cooldown() >= base", "\n    assert (\n        cooldown()\n        >= base\n    )  # floor\n"),
        ('"""Cooldown is at least the base."""', '"""Cooldown never drops below the base."""'),
        ('"""Limiter oracle."""', '"""Limiter oracle, rewritten."""'),
        ("[1, 2]", "[1,\n     2]"),
        # a new import, and a name added to an existing import line
        ("import sys\n", "import sys\nimport os\n"),
        ("from limiter import cooldown", "from limiter import burst, cooldown"),
        # an unrelated helper and an unfrozen test
        ("    return 1\n", "    return 2\n"),
        ("    def test_other(self):\n        assert True", "    def test_other(self):\n        assert 1 == 1"),
    ],
)
def test_edits_outside_the_frozen_tests_are_not_refused(tmp_path: Path, frozen: Path, old, new):
    _edit(tmp_path, old, new)
    assert _errors(tmp_path, frozen) == []


def test_adding_tests_is_not_refused(tmp_path: Path, frozen: Path):
    (tmp_path / TEST_FILE).write_text(
        ORACLE.replace("    def test_other(self):", "    def test_edge(self):\n        assert cooldown() < 99\n\n    def test_other(self):")
        + "\n\n@pytest.fixture\ndef big():\n    return 3600\n\n\ndef test_cap(big):\n    assert cooldown() < big\n",
        encoding="utf-8",
    )
    assert _errors(tmp_path, frozen) == []


def test_ids_are_matched_when_pytest_rootdir_is_not_the_product_root(tmp_path: Path):
    red = _freeze(tmp_path, {TEST_FILE: ORACLE}, ["test_limiter::test_cooldown"])
    record = yaml.safe_load(red.read_text(encoding="utf-8"))["red_oracle_tests"]
    assert [t["test"] for t in record["tests"]] == ["test_cooldown"]


# --- what is frozen whole ------------------------------------------------------

def test_a_file_the_core_cannot_split_keeps_the_file_hash(tmp_path: Path):
    data = "tests/data/expected.json"
    red = _freeze(tmp_path, {TEST_FILE: ORACLE, data: '{"cooldown": 30}\n'}, FAILED)
    record = yaml.safe_load(red.read_text(encoding="utf-8"))["red_oracle_tests"]
    assert (data, "bytes") in [(f["path"], f["form"]) for f in record["files"]]
    assert _errors(tmp_path, red) == []
    _edit(tmp_path, "30", "0", rel=data)
    errs = _errors(tmp_path, red)
    assert errs and f"{data} changed" in errs[0], errs


def test_a_named_test_the_core_cannot_find_freezes_its_module_whole(tmp_path: Path):
    source = "import pytest\n\nfor n in (1, 2):\n    globals()[f'test_{n}'] = lambda: None\n"
    red = _freeze(tmp_path, {TEST_FILE: source}, ["tests.test_limiter::test_1"])
    record = yaml.safe_load(red.read_text(encoding="utf-8"))["red_oracle_tests"]
    assert len(record["files"]) == 1 and record["files"][0]["form"] == "ast"
    _edit(tmp_path, "(1, 2)", "(1, 2, 3)")
    assert _errors(tmp_path, red)


def test_a_test_module_red_named_no_test_in_has_all_its_tests_frozen(tmp_path: Path):
    other = "tests/test_other.py"
    red = _freeze(
        tmp_path,
        {TEST_FILE: ORACLE, other: "def test_a():\n    assert 1\n\n\ndef test_b():\n    assert 2\n"},
        FAILED,
    )
    _edit(tmp_path, "assert 2", "assert 3", rel=other)
    assert any(f"{other}::test_b changed" in e for e in _errors(tmp_path, red))


# --- records written before the per-test freeze --------------------------------

def test_an_old_record_with_a_file_hash_is_checked_the_old_way(tmp_path: Path):
    (tmp_path / "tests").mkdir()
    (tmp_path / TEST_FILE).write_text(ORACLE, encoding="utf-8")
    red_file = tmp_path / "red.yaml"
    red_file.write_text(
        yaml.safe_dump({
            "changed_paths": [TEST_FILE],
            "red_oracle": compute_red_oracle_digest(tmp_path, [TEST_FILE]),
        }),
        encoding="utf-8",
    )
    assert _errors(tmp_path, red_file) == []
    _edit(tmp_path, "def helper():", "# a comment\ndef helper():")
    errs = _errors(tmp_path, red_file)
    assert errs and f"{TEST_FILE} changed after Declare" in errs[0], errs


def test_a_record_with_no_frozen_oracle_compares_nothing(tmp_path: Path):
    red_file = tmp_path / "red.yaml"
    red_file.write_text(yaml.safe_dump({"changed_paths": [TEST_FILE]}), encoding="utf-8")
    assert _errors(tmp_path, red_file) == []
