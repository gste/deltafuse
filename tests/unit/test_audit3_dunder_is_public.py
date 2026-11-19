"""A dunder attribute is public; a `_name` or a name-mangled `__name` is not.

Reported by the Fuseback quick-fix round (3.3.14): `_PRIVATE_ATTR` matched `._` anywhere, so a
Red test reading `type(x).__name__`, `__module__` or `__qualname__` was refused as one that
"accesses private symbols" - while the import rule of the same function exempts dunders.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core import integrity
from deltafuse.core.integrity import scan_changed_paths_for_private_test_access


@pytest.mark.parametrize("source", [
    "assert type(err).__name__ == 'LimitExceeded'\n",
    "assert limiter.__module__ == 'shop.limits'\n",
    "assert fn.__qualname__.endswith('consume')\n",
    "assert obj.__dict__ == {}\n",
])
def test_a_dunder_is_public(source: str):
    assert not integrity.test_source_uses_private_symbols(source)


@pytest.mark.parametrize("source", [
    "limiter._blocked_until['u'] = 0.0\n",
    "limiter.__blocked_until = {}\n",  # name-mangled: private, not a dunder
    "assert obj.__secret__x == 1\n",
    "assert type(x).__name__ and x._cache\n",  # a dunder beside a private access
])
def test_private_and_mangled_names_stay_private(source: str):
    assert integrity.test_source_uses_private_symbols(source)


def test_a_red_test_with_a_dunder_is_not_refused(tmp_path: Path):
    test = tmp_path / "tests" / "test_limit.py"
    test.parent.mkdir()
    test.write_text("def test_name():\n    assert type(ValueError()).__name__ == 'ValueError'\n", encoding="utf-8")
    assert scan_changed_paths_for_private_test_access(tmp_path, ["tests/test_limit.py"]) == []
