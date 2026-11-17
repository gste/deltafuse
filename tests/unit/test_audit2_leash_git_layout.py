"""Audit 2026-11-17 (df-leash): how the product sits in git. FW-2 (owner's decision R4: a product in
a subdirectory of a repository is refused by `init` and by the leash), FW-15 (the hook lets the
first commit through), FW-13 (a missing hook is said out loud)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    REPO_ROOT, cli, commit, env, git, leash, product_at, put, set_workflow, walk,
)


def _mono(tmp_path: Path) -> Path:
    mono = tmp_path / "mono"
    mono.mkdir()
    git(mono, "init", "-q")
    put(mono, "README.md", "mono\n")
    commit(mono, "root")
    return mono


# --- FW-2 -------------------------------------------------------------------------------

def test_init_refuses_a_subdirectory_of_a_repository(tmp_path):
    """FW-2: `init` installed there without a word; the hook was not installed (`.git` is one level
    up) and the leash compared repository-relative names with product-relative globs, so no edit
    was ever judged."""
    from deltafuse.core.installer import InstallationError, install

    svc = _mono(tmp_path) / "svc"
    with pytest.raises(InstallationError, match="subdirectory"):
        install(target_dir=svc, framework_root=REPO_ROOT)
    assert not (svc / ".deltafuse").exists()
    code, out = cli("init", svc, check=False)
    assert code != 0 and "subdirectory" in out, out


def test_init_still_takes_a_repository_root_a_worktree_and_no_git(tmp_path):
    from deltafuse.core.installer import install

    install(target_dir=tmp_path / "plain", framework_root=REPO_ROOT)
    mono = _mono(tmp_path)
    install(target_dir=mono, framework_root=REPO_ROOT)
    commit(mono, "scaffold")
    tree = tmp_path / "tree"
    git(mono, "worktree", "add", "-q", str(tree), "-b", "feature")
    install(target_dir=tree, framework_root=REPO_ROOT)


@pytest.mark.parametrize("script", ["init.sh", "init.ps1"])
def test_the_script_installers_refuse_a_subdirectory_too(tmp_path, script):
    """The twins of `deltafuse init`."""
    svc = _mono(tmp_path) / "svc"
    svc.mkdir()
    if script == "init.sh":
        exe = shutil.which("bash")
        argv = [exe, (REPO_ROOT / "scripts" / script).as_posix(), svc.as_posix()]
    else:
        exe = shutil.which("pwsh") or shutil.which("powershell")
        argv = [exe, "-NoProfile", "-File", str(REPO_ROOT / "scripts" / script), str(svc)]
    if exe is None:
        pytest.skip(f"no interpreter for {script}")
    proc = subprocess.run(argv, cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env())
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "subdirectory" in proc.stdout + proc.stderr, proc.stdout + proc.stderr
    assert not (svc / ".deltafuse").exists()


def _product_in_a_subdirectory(product_at, tmp_path) -> Path:
    root, _ = product_at("declared")
    mono = _mono(tmp_path)
    svc = mono / "svc"
    shutil.copytree(root, svc, ignore=shutil.ignore_patterns(".git"))
    commit(mono, "a product one level down")
    return svc


def test_the_leash_refuses_a_product_in_a_subdirectory(product_at, tmp_path):
    svc = _product_in_a_subdirectory(product_at, tmp_path)
    put(svc, "src/existing.py", "X = 2\n")
    code, out = cli("leash", svc, check=False)
    assert code == 2 and "subdirectory" in out, out


def test_advance_says_the_step_was_not_judged_there(product_at, tmp_path):
    """The twin entry point: `advance` reports it instead of a silent "no violations"."""
    from deltafuse.core.leash_run import leash_at_advance

    svc = _product_in_a_subdirectory(product_at, tmp_path)
    put(svc, "src/existing.py", "X = 2\n")
    verdict = leash_at_advance(next((svc / "docs" / "changes").glob("CHG-*")), svc)
    assert verdict["checked"] is False and "subdirectory" in verdict["reason"], verdict


# --- FW-15 ------------------------------------------------------------------------------

def _fresh_enforce_product(tmp_path: Path) -> Path:
    from deltafuse.core.installer import install

    root = tmp_path / "fresh"
    root.mkdir()
    git(root, "init", "-q")
    install(target_dir=root, framework_root=REPO_ROOT)
    set_workflow(root, leash="enforce")
    install(target_dir=root, framework_root=REPO_ROOT)
    assert (root / ".git" / "hooks" / "pre-commit").is_file()
    return root


def test_the_hook_lets_the_first_commit_through(tmp_path):
    """FW-15: with no commit there is nothing to judge against; `deltafuse leash` says "make an
    initial commit", and under enforce the hook refused that very commit."""
    root = _fresh_enforce_product(tmp_path)
    proc = commit(root, "scaffold", verify=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_the_second_commit_is_judged(tmp_path):
    """The bypass: only the commit that has no parent passes unjudged."""
    root = _fresh_enforce_product(tmp_path)
    assert commit(root, "scaffold", verify=True).returncode == 0
    put(root, "src/app.py", "x = 1\n")
    proc = commit(root, "code with no Change", verify=True)
    assert proc.returncode != 0 and "src/app.py" in proc.stdout + proc.stderr


def test_the_commit_that_installs_deltafuse_into_an_existing_repository_passes(tmp_path):
    """The same case one commit later: a service that already has history. The scaffold `init`
    writes (README templates, CHANGELOG.md, the CI workflow, .gitignore) is judged like any file
    now, and its base is a repository without DeltaFuse."""
    from deltafuse.core.installer import install

    root = tmp_path / "service"
    root.mkdir()
    git(root, "init", "-q")
    put(root, "README.md", "service\n")
    commit(root, "mainline")
    install(target_dir=root, framework_root=REPO_ROOT)
    set_workflow(root, leash="enforce")
    install(target_dir=root, framework_root=REPO_ROOT)
    proc = commit(root, "deltafuse", verify=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    put(root, "README.md", "service, edited with no Change\n")
    proc = commit(root, "next", verify=True)
    assert proc.returncode != 0 and "README.md" in proc.stdout + proc.stderr


def test_the_leash_command_still_asks_for_the_first_commit(tmp_path):
    root = _fresh_enforce_product(tmp_path)
    code, out = cli("leash", root, check=False)
    assert code == 2 and "initial commit" in out, out


# --- FW-13 ------------------------------------------------------------------------------

def _clone(root: Path, tmp_path: Path) -> Path:
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(root), str(clone)], check=True, capture_output=True, env=env())
    return clone


def test_a_fresh_clone_is_told_it_has_no_hook(product_at, tmp_path, monkeypatch):
    """FW-13: hooks are not cloned. On a fresh clone of an enforce product every commit went
    unjudged and nothing said so: `leash` and `validate-layout` both answered as if all was well."""
    monkeypatch.delenv("CI", raising=False)
    root, _ = product_at("converged")
    clone = _clone(root, tmp_path)
    code, data = leash(clone)
    assert code == 0 and data["warnings"] and "pre-commit" in data["warnings"][0], data
    code, out = cli("leash", clone, check=False)
    assert "deltafuse init" in out, out
    code, out = cli("validate-layout", clone, check=False)
    assert "pre-commit" in out and "deltafuse init" in out, out


def test_a_hooks_path_set_after_init_is_told_too(product_at, monkeypatch):
    """The twin: the hook is in .git/hooks, and git no longer runs hooks from there."""
    monkeypatch.delenv("CI", raising=False)
    root, _ = product_at("converged")
    git(root, "config", "core.hooksPath", ".husky")
    put(root, ".husky/pre-commit", "#!/bin/sh\nexit 0\n")
    _, data = leash(root)
    assert data["warnings"], data
    _, out = cli("validate-layout", root, check=False)
    assert "pre-commit" in out, out


def test_no_warning_where_the_hook_is_installed_or_the_leash_is_off(product_at, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    root, _ = product_at("converged")
    _, data = leash(root)
    assert data["warnings"] == [], data
    code, out = cli("validate-layout", root, check=False)
    assert code == 0 and "pre-commit" not in out, out
    (root / ".git" / "hooks" / "pre-commit").unlink()
    set_workflow(root, leash="off")
    commit(root, "the human turns the leash off")
    _, data = leash(root)
    assert data["warnings"] == [], data
