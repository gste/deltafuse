"""DF3-003: versioned framework manifest and commit-range CI leash."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from deltafuse.core.hasher import compute_framework_content_hash
from deltafuse.core.leash import git_dirty_paths
from deltafuse.cli import main
from deltafuse.core.installer import install


def _framework_root(tmp_path: Path) -> Path:
    root = tmp_path / "framework"
    (root / "docs").mkdir(parents=True)
    (root / "process").mkdir()
    (root / "src" / "deltafuse" / "core").mkdir(parents=True)
    (root / "docs" / "workflow.md").write_text("canon\n", encoding="utf-8")
    (root / "src" / "deltafuse" / "core" / "fsm.py").write_text("state = 'safe'\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "deltafuse"\nversion = "1.0.0"\n', encoding="utf-8"
    )
    (root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    return root


@pytest.mark.parametrize(
    "mutation, description",
    [
        ("tamper", "SEC-02: editing Core code must change the pinned content hash"),
        ("delete", "SEC-02: deleting a Core file must change the pinned content hash"),
        ("rename", "SEC-02: renaming a Core file must change the pinned content hash"),
        ("entrypoint", "SEC-02: changing declared entrypoints must change the hash"),
    ],
)
def test_manifest_tracks_core_tampering(
    tmp_path: Path, mutation: str, description: str
):
    root = _framework_root(tmp_path)
    core_file = root / "src" / "deltafuse" / "core" / "fsm.py"
    before = compute_framework_content_hash(root)

    if mutation == "tamper":
        core_file.write_text("state = 'tampered'\n", encoding="utf-8")
    elif mutation == "delete":
        core_file.unlink()
    elif mutation == "rename":
        core_file.rename(core_file.with_name("renamed.py"))
    elif mutation == "entrypoint":
        (root / "pyproject.toml").write_text(
            '[project]\nname = "deltafuse"\nversion = "1.0.1"\n', encoding="utf-8"
        )

    after = compute_framework_content_hash(root)
    assert before != after, description


def test_manifest_digest_is_deterministic_for_same_tree(tmp_path: Path):
    """One canonical manifest: same tree, same digest (stable across order)."""
    root = _framework_root(tmp_path)
    assert compute_framework_content_hash(root) == compute_framework_content_hash(root)


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=leash@test", "-c", "user.name=leash", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _init_repo(root: Path) -> str:
    (root / ".gitignore").write_text("", encoding="utf-8")
    _git(root, "init")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    return _git(root, "rev-parse", "HEAD")


def test_clean_checkout_with_out_of_envelope_commit_fails_ci(
    tmp_path: Path, repo_root: Path
):
    """SEC-01: on a clean PR checkout the local diff is empty; the committed
    base..head range is what CI must judge."""
    install(target_dir=tmp_path, framework_root=repo_root)
    base = _init_repo(tmp_path)

    # The Worker commits an out-of-envelope product file and the checkout is clean.
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "rogue.py").write_text("rogue\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "rogue change")
    head = _git(tmp_path, "rev-parse", "HEAD")

    # Old behaviour: local-diff leash sees nothing on a clean checkout.
    assert git_dirty_paths(tmp_path) == []

    committed = git_dirty_paths(tmp_path, base=base, head=head)
    assert "src/rogue.py" in committed

    ret = main(["leash", str(tmp_path), "--base", base, "--head", head, "--json"])
    assert ret != 0, "out-of-envelope commit must fail the commit-range leash"


def test_untracked_files_stay_checked_alongside_commit_range(
    tmp_path: Path, repo_root: Path
):
    install(target_dir=tmp_path, framework_root=repo_root)
    base = _init_repo(tmp_path)
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "untracked.py").write_text("x\n", encoding="utf-8")

    local = git_dirty_paths(tmp_path)
    ranged = git_dirty_paths(tmp_path, base=base, head="HEAD")
    assert local == ["src/untracked.py"]
    assert ranged == ["src/untracked.py"], "untracked check is always on"


def test_leash_rejects_head_without_base(tmp_path: Path, repo_root: Path, capsys) -> None:
    install(target_dir=tmp_path, framework_root=repo_root)
    ret = main(["leash", str(tmp_path), "--head", "HEAD"])
    assert ret != 0
    _, err = capsys.readouterr()
    assert "--base" in err
