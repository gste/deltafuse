"""`workflow.test_commands`, `workflow.evidence_timeout` and `context.*` are the human's (B-6).

Audit 3: a regression narrowed with `-Dtest=` was refused with "declare the command with it in
workflow.test_commands"; the Worker added it there and the narrowed run was then authentic
regression and verification, and the leash called the diff "inside the envelope" - only
`workflow.leash` and `workflow.code_roots` were guarded.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from tests.fixtures.evidence_kit import product, write
from tests.fixtures.leash_walk import commit, leash, product_at, walk  # noqa: F401 - fixtures

PYTEST = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider"]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _config(root: Path) -> dict:
    return yaml.safe_load((root / ".deltafuse" / "config.yaml").read_text(encoding="utf-8"))


def _save(root: Path, data: dict) -> None:
    (root / ".deltafuse" / "config.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _narrowing_product(tmp_path: Path, repo_root: Path):
    builder = product(tmp_path, repo_root, allowed=["src/**", "tests/**"])
    write(tmp_path / "tests/test_a.py", "def test_a():\n    assert True\n")
    write(tmp_path / "tests/test_b.py", "def test_b():\n    assert True\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "core.autocrlf", "false")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    narrowed = " ".join(["python", "-m", "pytest", "-p", "no:cacheprovider", "tests/test_a.py"])
    data = _config(tmp_path)
    data.setdefault("workflow", {})["test_commands"] = [narrowed]
    _save(tmp_path, data)  # the Worker's edit, not committed
    return builder


def test_an_uncommitted_test_command_does_not_make_a_narrowed_run_the_suite(tmp_path: Path, repo_root: Path):
    builder = _narrowing_product(tmp_path, repo_root)
    reg = run_evidence(builder.change_dir, phase="regression", task="TASK-001",
                       argv=[*PYTEST, "tests/test_a.py"], changed_paths=[])
    assert any("names single test files" in e for e in reg.errors), reg.errors
    assert not reg.authentic


def test_the_gate_reads_the_committed_test_commands_too(tmp_path: Path, repo_root: Path):
    """The twin path: a record taken before the edit is judged again at the gate."""
    builder = _narrowing_product(tmp_path, repo_root)
    run_evidence(builder.change_dir, phase="regression", task="TASK-001",
                 argv=[*PYTEST, "tests/test_a.py"], changed_paths=[])
    errors = check_gate(builder.change_dir, "implemented")
    assert any("names single test files" in e for e in errors), errors


def test_the_refusal_addresses_the_human(tmp_path: Path, repo_root: Path):
    builder = _narrowing_product(tmp_path, repo_root)
    reg = run_evidence(builder.change_dir, phase="regression", task="TASK-001",
                       argv=[*PYTEST, "-k", "test_a"], changed_paths=[])
    text = " ".join(reg.errors)
    assert "the human declares it in workflow.test_commands" in text, reg.errors
    assert "declare the command with it" not in text


@pytest.mark.parametrize("edit", [
    lambda d: d["workflow"].__setitem__("test_commands", ["pytest tests/test_banner.py"]),
    lambda d: d["workflow"].__setitem__("evidence_timeout", 5),
    lambda d: d.__setitem__("context", {"max_tokens": 10_000_000}),
], ids=["test_commands", "evidence_timeout", "context"])
def test_a_commit_that_changes_a_human_setting_is_a_leash_violation(product_at, edit):
    root, _ = product_at("decomposed")
    base = _git(root, "rev-parse", "HEAD")
    data = _config(root)
    edit(data)
    _save(root, data)
    commit(root, "worker edits the config")
    code, payload = leash(root, "--base", base, "--head", _git(root, "rev-parse", "HEAD"))
    assert code != 0, payload
    assert any("human's setting" in v and "config.yaml" in v for v in payload["violations"]), payload
