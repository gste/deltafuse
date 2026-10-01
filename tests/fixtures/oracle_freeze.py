"""A small test tree frozen as Red would freeze it (core/oracle.py).

Shared by the unit tests of the frozen Red oracle: freeze, edit as Implement
might, and ask the check the Green evidence call and the implemented gate use.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from deltafuse.core.fsm import frozen_oracle_errors
from deltafuse.core.oracle import freeze_red_oracle

TEST_FILE = "tests/test_limiter.py"

ORACLE = '''"""Limiter oracle."""
import sys

import pytest
from limiter import cooldown


@pytest.fixture
def base():
    return 30


def helper():
    return 1


def test_cooldown(base):
    """Cooldown is at least the base."""
    assert cooldown() >= base


@pytest.mark.parametrize("n", [1, 2])
def test_cooldown_scales(n):
    assert cooldown() * n >= 30 * n


class TestWindow:
    limit = 30

    def test_window(self):
        assert cooldown() >= self.limit

    def test_other(self):
        assert True
'''

FAILED = [
    "tests.test_limiter::test_cooldown",
    "tests.test_limiter::test_cooldown_scales[1]",
    "tests.test_limiter::test_cooldown_scales[2]",
    "tests.test_limiter.TestWindow::test_window",
]


def freeze(root: Path, files: dict[str, str], failed: list[str], declared: list[str] | None = None) -> Path:
    """Write `files`, record Red over `declared` (default: all of them)."""
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    declared = declared if declared is not None else list(files)
    record = {"phase": "red", "changed_paths": declared, "tests": {"failed": list(failed)}}
    frozen = freeze_red_oracle(root, declared, failed)
    assert frozen is not None
    record["red_oracle_tests"] = frozen
    red_file = root / "red.yaml"
    red_file.write_text(yaml.safe_dump(record), encoding="utf-8")
    return red_file


def record_of(red_file: Path) -> dict:
    return yaml.safe_load(red_file.read_text(encoding="utf-8"))["red_oracle_tests"]


def errors(root: Path, red_file: Path) -> list[str]:
    return frozen_oracle_errors(red_file, root, "green evidence 'TASK-001.yaml'")


def edit(root: Path, old: str, new: str, rel: str = TEST_FILE) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
