"""Audit 2026-11-17 (df-leash), FW-12: the CI workflow the installer copies. Without a usable base
(a new branch, a force push) it ran `deltafuse leash .` on a clean checkout, which has no diff:
it judged nothing and passed."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    REPO_ROOT, commit, env, git, product_at, put, walk,
)

ZEROS = "0" * 40
TEMPLATE = REPO_ROOT / "process" / "templates" / ".github" / "workflows" / "deltafuse-leash.yml"


def _leash_step(event: str, before: str, after: str) -> str:
    workflow = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    script = next(step["run"] for step in workflow["jobs"]["leash"]["steps"] if step.get("name") == "Leash")
    for expression, value in {
        "${{ github.event_name }}": event,
        "${{ github.event.pull_request.base.sha }}": before,
        "${{ github.event.pull_request.head.sha }}": after,
        "${{ github.event.before }}": before,
        "${{ github.event.after }}": after,
    }.items():
        script = script.replace(expression, value)
    assert "${{" not in script, script
    return script


def _run_step(clone: Path, script: str) -> subprocess.CompletedProcess:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("no bash")
    environment = env()
    environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment["PATH"]
    environment["CI"] = "true"
    return subprocess.run([bash, "-e", "-c", script], cwd=clone, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=environment)


def _clean_checkout(root: Path, tmp_path: Path) -> Path:
    clone = tmp_path / "checkout"
    subprocess.run(["git", "clone", "-q", str(root), str(clone)], check=True, capture_output=True, env=env())
    return clone


def _with_a_stray_commit(product_at):
    root, _ = product_at("declared")
    put(root, "src/existing.py", "X = 'outside TASK-001'\n")
    commit(root, "stray")  # --no-verify
    return root


@pytest.mark.parametrize("before", [ZEROS, "", "1234567890123456789012345678901234567890"])
def test_without_a_usable_base_the_head_commit_is_still_judged(product_at, tmp_path, before):
    clone = _clean_checkout(_with_a_stray_commit(product_at), tmp_path)
    head = git(clone, "rev-parse", "HEAD").stdout.strip()
    proc = _run_step(clone, _leash_step("push", before, head))
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "src/existing.py" in proc.stdout + proc.stderr, proc.stdout + proc.stderr


def test_with_a_base_the_range_is_judged_as_before(product_at, tmp_path):
    clone = _clean_checkout(_with_a_stray_commit(product_at), tmp_path)
    head = git(clone, "rev-parse", "HEAD").stdout.strip()
    base = git(clone, "rev-parse", "HEAD~1").stdout.strip()
    for event in ("push", "pull_request"):
        proc = _run_step(clone, _leash_step(event, base, head))
        assert proc.returncode != 0 and "src/existing.py" in proc.stdout + proc.stderr, proc.stdout + proc.stderr


def test_a_clean_range_passes(product_at, tmp_path):
    root, _ = product_at("declared")
    clone = _clean_checkout(root, tmp_path)
    head = git(clone, "rev-parse", "HEAD").stdout.strip()
    proc = _run_step(clone, _leash_step("push", ZEROS, head))
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_the_first_commit_of_a_history_passes_with_a_note(product_at, tmp_path):
    root, _ = product_at("init")
    clone = _clean_checkout(root, tmp_path)
    head = git(clone, "rev-parse", "HEAD").stdout.strip()
    proc = _run_step(clone, _leash_step("push", ZEROS, head))
    assert proc.returncode == 0 and "first commit" in proc.stdout, proc.stdout + proc.stderr


def test_the_bundled_copy_is_the_template(repo_root):
    bundled = repo_root / "src" / "deltafuse" / "assets" / "templates" / ".github" / "workflows" / "deltafuse-leash.yml"
    assert bundled.read_bytes().replace(b"\r\n", b"\n") == TEMPLATE.read_bytes().replace(b"\r\n", b"\n")
