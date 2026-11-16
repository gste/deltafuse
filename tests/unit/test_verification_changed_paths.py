"""Verification records the Core-computed changed paths, like every other phase.

Audit 2026-11-16 (df-gates #10): with no `--changed-path`, Red, Green and regression record the
dirty set the Core computes, but verification recorded none and then refused itself for not
listing it - an honest verification on a tree with the Change's uncommitted work was never
authentic, and the converged gate accepted it anyway.
"""

from __future__ import annotations

import sys
from pathlib import Path

from deltafuse.core.evidence import run_evidence
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder
from tests.fixtures.git import git


def test_verification_on_a_dirty_tree_is_authentic(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-270", title="Verify").step_through_decompose()
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_add.py").write_text(
        "import sys\nsys.path.insert(0, 'src')\nfrom calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    (tmp_path / "src" / "calc.py").write_text("def add(a, b):\n    return b + a\n", encoding="utf-8")

    ver = run_evidence(builder.change_dir, phase="verification",
                       argv=[sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "tests"])
    assert ver.payload["changed_paths"] == ["src/calc.py"]
    assert ver.authentic, ver.errors
