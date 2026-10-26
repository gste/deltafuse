"""A Red test that fails on an error in its own code is not Red (core/red_cause.py).

ref-m02-339 (2026-10-05): `set(sys.modules) - before` intersected with a tuple raised TypeError
whatever the product did; Red was recorded, the oracle frozen, and Implement could only halt.
Checked against every Red report of the bench runs to date: 628 failed tests, this one flagged.
"""

from __future__ import annotations

import sys
from pathlib import Path

from deltafuse.core.evidence import OWN_CODE_RED_CATEGORY, run_evidence
from deltafuse.core.installer import install
from deltafuse.core.red_cause import own_code_failures
from deltafuse.core.test_reports import FAILED
from deltafuse.core.test_reports import TestReport as Report
from tests.fixtures.change_builder import MockChangeBuilder

TEST_FILE = '''import sys
import pytest

NETWORKY = ("socket", "http")


def test_own_bug():
    before = set(sys.modules)
    import shop.cart

    new = set(sys.modules) - before
    assert not (new & NETWORKY)


def test_product_value():
    from shop.cart import Cart

    tags = Cart().tags()
    assert tags & ("a",)


def test_name_typo():
    assert totl == 0


def test_with_fixture(cart):
    assert cart & ("a",)
'''


def _product(tmp_path: Path) -> Path:
    (tmp_path / "src" / "shop").mkdir(parents=True)
    (tmp_path / "src" / "shop" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "shop" / "cart.py").write_text("class Cart:\n    pass\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_shop.py").write_text(TEST_FILE, encoding="utf-8")
    return tmp_path


def _line(text: str) -> int:
    return TEST_FILE.splitlines().index(text) + 1


def _report(**failures: tuple[str, str]) -> Report:
    names = {f"tests.test_shop::{k}": v for k, v in failures.items()}
    return Report("junitxml", {n: FAILED for n in names}, names)


def _tb(line_text: str, exc: str) -> tuple[str, str]:
    return exc, f"tests\\test_shop.py:{_line(line_text)}: in test\n    {line_text.strip()}\nE   {exc}"


def test_an_operator_error_between_builtins_on_a_line_without_product_is_refused(tmp_path):
    root = _product(tmp_path)
    report = _report(
        test_own_bug=_tb("    assert not (new & NETWORKY)", "TypeError: unsupported operand type(s) for &: 'set' and 'tuple'")
    )
    found = own_code_failures(report, root)
    assert [name for name, _ in found] == ["tests.test_shop::test_own_bug"]
    assert "tests/test_shop.py:" in found[0][1]


def test_the_same_error_on_a_value_from_the_product_stays_red(tmp_path):
    root = _product(tmp_path)
    report = _report(
        test_product_value=_tb("    assert tags & (\"a\",)", "TypeError: unsupported operand type(s) for &: 'list' and 'tuple'"),
        test_with_fixture=_tb("    assert cart & (\"a\",)", "TypeError: unsupported operand type(s) for &: 'list' and 'tuple'"),
    )
    assert own_code_failures(report, root) == []


def test_a_name_the_test_never_bound_is_refused(tmp_path):
    root = _product(tmp_path)
    report = _report(test_name_typo=_tb("    assert totl == 0", "NameError: name 'totl' is not defined"))
    assert [name for name, _ in own_code_failures(report, root)] == ["tests.test_shop::test_name_typo"]


def test_a_missing_product_api_and_an_error_raised_in_product_code_stay_red(tmp_path):
    root = _product(tmp_path)
    in_product = (
        "TypeError: unsupported operand type(s) for &: 'set' and 'tuple'",
        "tests\\test_shop.py:9: in test_own_bug\n    import shop.cart\nsrc\\shop\\cart.py:2: in <module>\nE   TypeError",
    )
    report = _report(
        test_product_value=_tb("    tags = Cart().tags()", "AttributeError: 'Cart' object has no attribute 'tags'"),
        test_own_bug=in_product,
    )
    assert own_code_failures(report, root) == []


def test_evidence_refuses_such_a_red_and_the_gate_reads_it(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-150", title="Own bug").step_through_decompose()
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_task-001.py").write_text(
        "import sys\n\nNET = ('socket',)\n\n\ndef test_in_process():\n"
        "    new = set(sys.modules)\n    assert not (new & NET)\n",
        encoding="utf-8",
    )
    red = run_evidence(
        builder.change_dir,
        phase="red",
        task="TASK-001",
        argv=[sys.executable, "-m", "pytest", "tests/test_task-001.py"],
        changed_paths=["tests/test_task-001.py"],
    )
    assert red.payload["failure_category"] == OWN_CODE_RED_CATEGORY
    assert not red.authentic
    assert any("fail on an error in their own code" in e and "test_in_process" in e for e in red.errors)
