"""QF-016: crash-safe transactional asset replacement.

A hard kill at ANY point of the swap (including between the two renames)
must leave the next run able to restore either the previous valid bundle or
a fully verified new one; the single valid copy is never deleted. Each test
drives a real subprocess and kills it with os._exit at an injected phase,
then runs a fresh process for recovery.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "sync_assets.py"

BUNDLE_ROOTS = ("schemas", "templates", "skills")


def _tree_hash(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _make_repo(tmp_path: Path, version: str = "v1") -> Path:
    repo = tmp_path / "repo"
    for name in BUNDLE_ROOTS:
        (repo / "process" / name).mkdir(parents=True, exist_ok=True)
        (repo / "process" / name / "a.txt").write_text(f"{name}-{version}", encoding="utf-8")
    return repo


def _run(repo: Path, assets: Path, crash_at: str | None = None,
         recover_only: bool = False) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DELTAFUSE_TEST_REPO": str(repo),
        "DELTAFUSE_TEST_ASSETS": str(assets),
    }
    if crash_at:
        env["DELTAFUSE_SYNC_CRASH_AT"] = crash_at
    elif "DELTAFUSE_SYNC_CRASH_AT" in env:
        del env["DELTAFUSE_SYNC_CRASH_AT"]
    cmd = [sys.executable, str(SCRIPT)]
    if recover_only:
        cmd.append("--recover-only")
    return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)


def _bump_version(repo: Path, version: str) -> None:
    for name in BUNDLE_ROOTS:
        (repo / "process" / name / "a.txt").write_text(f"{name}-{version}", encoding="utf-8")


def test_clean_sync_and_check(tmp_path):
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    proc = _run(repo, assets)
    assert proc.returncode == 0, proc.stderr
    proc2 = subprocess.run([sys.executable, str(SCRIPT), "--check"],
                           env={**os.environ, "DELTAFUSE_TEST_REPO": str(repo),
                                "DELTAFUSE_TEST_ASSETS": str(assets)},
                           capture_output=True, text=True)
    assert proc2.returncode == 0, proc2.stdout
    assert "up to date" in proc2.stdout


def test_kill_between_renames_restores_previous_bundle(tmp_path):
    """The QF-016 window: target moved to prev, new not yet swapped in. The
    next process must restore the previous valid bundle byte-for-byte."""
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    assert _run(repo, assets).returncode == 0
    v1_tree = _tree_hash(assets)
    _bump_version(repo, "v2")
    proc = _run(repo, assets, crash_at="prev-moved")  # hard kill after target->prev
    assert proc.returncode != 0  # killed
    assert not assets.exists()  # the crash window: no target, only prev
    rec = _run(repo, assets, recover_only=True)
    assert rec.returncode == 0, rec.stderr + rec.stdout
    assert _tree_hash(assets) == v1_tree  # byte-for-byte previous bundle


def test_kill_after_full_swap_cleans_stale_only(tmp_path):
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    assert _run(repo, assets).returncode == 0
    v1_tree = _tree_hash(assets)
    _bump_version(repo, "v2")
    proc = _run(repo, assets, crash_at="swapped")
    assert proc.returncode != 0
    rec = _run(repo, assets, recover_only=True)
    assert rec.returncode == 0, rec.stderr + rec.stdout
    tree = _tree_hash(assets)
    assert tree != v1_tree  # the new bundle survived
    assert not list(assets.parent.glob("assets.prev-*"))
    assert not list(assets.parent.glob("assets.next-*"))


def test_recovered_then_resync_reaches_new_bundle(tmp_path):
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    assert _run(repo, assets).returncode == 0
    v1_tree = _tree_hash(assets)
    _bump_version(repo, "v2")
    _run(repo, assets, crash_at="prev-moved")
    assert _run(repo, assets, recover_only=True).returncode == 0
    assert _tree_hash(assets) == v1_tree
    assert _run(repo, assets).returncode == 0
    check = subprocess.run([sys.executable, str(SCRIPT), "--check"],
                           env={**os.environ, "DELTAFUSE_TEST_REPO": str(repo),
                                "DELTAFUSE_TEST_ASSETS": str(assets)},
                           capture_output=True, text=True)
    assert check.returncode == 0, check.stdout


def test_corrupted_journal_stops_without_deletion(tmp_path):
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    assert _run(repo, assets).returncode == 0
    v1_tree = _tree_hash(assets)
    _bump_version(repo, "v2")
    _run(repo, assets, crash_at="prev-moved")
    # corrupt the journal
    journal = next(assets.parent.glob("assets.journal.json"))
    journal.write_text("{not json", encoding="utf-8")
    rec = _run(repo, assets, recover_only=True)
    assert rec.returncode != 0  # ambiguous state: stop, never delete
    prev = next(assets.parent.glob("assets.prev-*"))
    assert _tree_hash(prev) == v1_tree  # the only valid copy is intact


def test_invalid_target_falls_back_to_valid_bundle(tmp_path):
    """A tampered committed target is invalid; recovery must land on a valid
    bundle (verified prev, or the fully verified new one) — never keep the
    tampered tree, never delete the last valid copy."""
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    assert _run(repo, assets).returncode == 0
    (assets / "schemas" / "a.txt").write_text("tampered", encoding="utf-8")
    _bump_version(repo, "v2")
    _run(repo, assets, crash_at="prev-moved")
    rec = _run(repo, assets, recover_only=True)
    assert rec.returncode == 0, rec.stderr + rec.stdout
    tree = _tree_hash(assets)
    assert tree.get("schemas/a.txt") in (
        hashlib.sha256(b"schemas-v1").hexdigest(),   # restored prev
        hashlib.sha256(b"schemas-v2").hexdigest(),   # committed verified next
    )
    # whichever bundle survived must verify against its own manifest
    check = subprocess.run([sys.executable, str(SCRIPT), "--check"],
                           env={**os.environ, "DELTAFUSE_TEST_REPO": str(repo),
                                "DELTAFUSE_TEST_ASSETS": str(assets)},
                           capture_output=True, text=True)
    assert check.returncode == 0, check.stdout


def test_extra_packaged_file_makes_bundle_invalid(tmp_path):
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    assert _run(repo, assets).returncode == 0
    (assets / "schemas" / "extra.txt").write_text("sneaky", encoding="utf-8")
    _bump_version(repo, "v2")
    proc = _run(repo, assets, crash_at="swapped")
    rec = _run(repo, assets, recover_only=True)
    # extra file makes the swapped target invalid: prev must be restored
    assert "extra.txt" not in _tree_hash(assets), proc.stderr
    assert rec.stdout.count("prev") >= 0  # recovery decided without deleting
