"""Audit 2026-11-16 (df-leash): what the pre-commit hook, `deltafuse leash` and `advance` see in git.

Each product here is an `enforce` product with the generated hook installed; a write the envelope
refuses must not reach a commit (or a transition) by way of how git reports it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from deltafuse.core.installer import install
from deltafuse.core.leash import sync_leash_hook
from tests.fixtures.change_builder import MockChangeBuilder


def _env(repo_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(repo_root / "src"), str(repo_root)])
    env["DELTAFUSE_PYTHON"] = Path(sys.executable).as_posix()
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "w"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "w@x"
    return env


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=root,
                          capture_output=True, text=True, encoding="utf-8", env=_env(repo_root))
    if check and proc.returncode != 0:
        raise AssertionError(f"git {args}: {proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    return proc


def set_workflow(root: Path, **values) -> None:
    cfg = root / ".deltafuse" / "config.yaml"
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    data["workflow"].update(values)
    cfg.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def product(tmp_path: Path, repo_root: Path, *, intake: bool = True) -> Path:
    """An enforce product, hook installed, one Change in intake (ready: analyze), src/app.py committed."""
    root = tmp_path / "prod"
    root.mkdir()
    install(target_dir=root, framework_root=repo_root)
    set_workflow(root, leash="enforce")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "app.py").write_text("print('original')\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "scaffold")
    if intake:
        MockChangeBuilder(root, change_id="CHG-001", title="t").step_intake()
        git(root, "add", "-A")
        git(root, "commit", "-q", "--no-verify", "-m", "intake")
    sync_leash_hook(root, "enforce")
    assert (root / ".git" / "hooks" / "pre-commit").is_file()
    return root


def commit(root: Path, msg: str = "worker") -> subprocess.CompletedProcess:
    return git(root, "commit", "-q", "-m", msg, check=False)


def test_control_a_plain_src_write_is_refused(tmp_path: Path, repo_root: Path):
    root = product(tmp_path, repo_root)
    (root / "src" / "app.py").write_text("print('evil')\n", encoding="utf-8")
    git(root, "add", "-A")
    assert commit(root).returncode != 0


def test_a_non_ascii_product_path_is_judged(tmp_path: Path, repo_root: Path):
    """df-leash #4: under core.quotePath git named `src/модуль.py` as "src/\\320\\274...", which matched no
    glob, so a Cyrillic file in src/ committed in Analyze."""
    root = product(tmp_path, repo_root)
    (root / "src" / "модуль.py").write_text("print('evil')\n", encoding="utf-8")
    git(root, "add", "-A")
    proc = commit(root)
    assert proc.returncode != 0
    assert "src/модуль.py" in proc.stdout + proc.stderr


def test_a_rename_out_of_src_shows_the_deletion(tmp_path: Path, repo_root: Path):
    """df-leash #5: with rename detection `git diff --name-only` named only the new path, so
    `git mv src/app.py docs/intake/app.py` removed product code in Analyze unseen."""
    root = product(tmp_path, repo_root)
    (root / "docs" / "intake").mkdir(parents=True, exist_ok=True)
    git(root, "mv", "src/app.py", "docs/intake/app.py")
    proc = commit(root)
    assert proc.returncode != 0
    assert "src/app.py" in proc.stdout + proc.stderr


def test_ci_judges_a_pr_from_its_merge_base(tmp_path: Path, repo_root: Path):
    """df-leash #15: CI diffed `base..head` (tree to tree). When the base branch moved on after the PR
    branched, its own new commits read as the PR's writes and the PR was refused for them."""
    from deltafuse.core.leash import git_dirty_paths
    from deltafuse.core.leash_run import run_leash

    root = tmp_path / "p"
    root.mkdir()
    install(target_dir=root, framework_root=repo_root)
    set_workflow(root, leash="enforce")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "scaffold")
    git(root, "checkout", "-q", "-b", "pr")
    MockChangeBuilder(root, change_id="CHG-001", title="t").step_intake()
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "intake")
    pr_head = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "checkout", "-q", "main")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "hotfix.py").write_text("x = 1\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "hotfix on main")
    base = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "checkout", "-q", "pr")
    paths = git_dirty_paths(root, base=base, head=pr_head)
    assert "src/hotfix.py" not in paths
    payload = run_leash(root, base=base, head=pr_head)
    assert payload["violations"] == [], payload


def test_ci_still_refuses_the_prs_own_write(tmp_path: Path, repo_root: Path):
    from deltafuse.core.leash_run import run_leash

    root = tmp_path / "p"
    root.mkdir()
    install(target_dir=root, framework_root=repo_root)
    set_workflow(root, leash="enforce")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "scaffold")
    git(root, "checkout", "-q", "-b", "pr")
    MockChangeBuilder(root, change_id="CHG-001", title="t").step_intake()
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "evil.py").write_text("x = 1\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "intake")
    pr_head = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "checkout", "-q", "main")
    (root / "README.md").write_text("moved on\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "main moved")
    base = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "checkout", "-q", "pr")
    payload = run_leash(root, base=base, head=pr_head)
    assert any("src/evil.py" in v for v in payload["violations"]), payload


def test_the_hook_judges_what_is_staged_not_the_working_tree(tmp_path: Path, repo_root: Path):
    """df-leash #1: the hook diffed the working tree against HEAD while git commits the index: a src/
    write staged and then reverted in the working tree committed unseen."""
    root = product(tmp_path, repo_root)
    app = root / "src" / "app.py"
    original = app.read_bytes()
    app.write_text("print('evil')\n", encoding="utf-8")
    git(root, "add", "src/app.py")
    app.write_bytes(original)
    proc = commit(root)
    assert proc.returncode != 0, git(root, "show", "HEAD:src/app.py").stdout
    assert "src/app.py" in proc.stdout + proc.stderr


def test_the_hook_judges_staged_bytes_of_a_structural_artifact(tmp_path: Path, repo_root: Path):
    """The bytes judged are the staged ones: a hand-written routing.yaml staged, the working tree then
    set back, is still a hand-written artifact in the commit."""
    root = product(tmp_path, repo_root)
    routing = root / "docs" / "changes" / "CHG-001" / "routing.yaml"
    routing.write_text("change: CHG-001\nclaims: {}\n", encoding="utf-8")
    git(root, "add", "-A")
    routing.unlink()
    proc = commit(root)
    assert proc.returncode != 0
    assert "written by hand" in proc.stdout + proc.stderr


def test_the_hook_does_not_judge_what_is_left_out_of_the_commit(tmp_path: Path, repo_root: Path):
    root = product(tmp_path, repo_root)
    (root / "src" / "app.py").write_text("print('later')\n", encoding="utf-8")  # not staged
    (root / "AGENTS.md").write_text("notes\n", encoding="utf-8")
    git(root, "add", "AGENTS.md")
    proc = commit(root)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_the_init_scripts_write_the_installers_hook(repo_root: Path):
    """init.sh and init.ps1 write the same pre-commit hook as the Python installer."""
    import re

    from deltafuse.core.leash import HOOK_SCRIPT

    sh = (repo_root / "scripts" / "init.sh").read_text(encoding="utf-8")
    block = re.search(r"HOOK_SCRIPT=\$\(cat <<'EOF'\n(.*?)\nEOF\n\)", sh, re.S)
    assert block is not None and block.group(1) + "\n" == HOOK_SCRIPT
    ps1 = (repo_root / "scripts" / "init.ps1").read_text(encoding="utf-8")
    body = re.search(r"\$script = \(@\((.*?)\) -join", ps1, re.S).group(1)
    lines = [re.sub(r"`(.)", r"\1", m) for m in re.findall(r'^\s*"(.*)",?\s*$', body, re.M)]
    assert "\n".join(lines) + "\n" == HOOK_SCRIPT
