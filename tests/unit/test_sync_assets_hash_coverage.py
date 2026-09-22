"""QF-023: every shipped regular file of the asset bundle — including
__init__.py — carries a manifest hash; no link/reparse point is accepted.

Red evidence: `__init__.py` was mandatory in the exact file set but absent
from the manifest hashes, so swapping it was undetectable; the reparse
rejection relied on a realpath string comparison without a dedicated
mutation matrix.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "sync_assets.py"

BUNDLE_ROOTS = ("schemas", "templates", "skills")


def _tree_hash(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _make_repo(tmp_path: Path, version: str = "v1") -> Path:
    repo = tmp_path / "repo"
    for name in BUNDLE_ROOTS:
        (repo / "process" / name).mkdir(parents=True, exist_ok=True)
        (repo / "process" / name / "a.txt").write_text(
            f"{name}-{version}", encoding="utf-8"
        )
    return repo


def _run(repo: Path, assets: Path, *args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DELTAFUSE_TEST_REPO": str(repo),
        "DELTAFUSE_TEST_ASSETS": str(assets),
    }
    env.pop("DELTAFUSE_SYNC_CRASH_AT", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], env=env,
        capture_output=True, text=True, timeout=120,
    )


def _manifest_files(assets: Path) -> dict:
    return json.loads((assets / "manifest.json").read_text(encoding="utf-8"))["files"]


# ------------------------------------------------------- hash coverage


def test_init_py_is_hashed_in_manifest(tmp_path):
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    assert _run(repo, assets).returncode == 0
    files = _manifest_files(assets)
    assert "__init__.py" in files, files
    assert files["__init__.py"] == hashlib.sha256(
        (assets / "__init__.py").read_bytes()
    ).hexdigest()


def test_tampered_init_py_detected_by_check(tmp_path):
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    assert _run(repo, assets).returncode == 0
    (assets / "__init__.py").write_text("evil", encoding="utf-8")
    proc = _run(repo, assets, "--check")
    assert proc.returncode != 0, proc.stdout
    assert "__init__.py" in proc.stdout


def test_tampered_init_py_invalidates_bundle(tmp_path, monkeypatch):
    """_verify_bundle rejects a swapped package marker."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    monkeypatch.setenv("DELTAFUSE_TEST_REPO", str(_make_repo(tmp_path)))
    monkeypatch.setenv("DELTAFUSE_TEST_ASSETS", str(tmp_path / "assets"))
    import importlib

    import sync_assets

    importlib.reload(sync_assets)
    assets = tmp_path / "assets"
    sync_assets.sync(assets)
    (assets / "__init__.py").write_text("evil", encoding="utf-8")
    with pytest.raises(RuntimeError, match="__init__.py"):
        sync_assets._verify_bundle(assets)


def test_removed_marker_and_extra_file_detected(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    monkeypatch.setenv("DELTAFUSE_TEST_REPO", str(_make_repo(tmp_path)))
    monkeypatch.setenv("DELTAFUSE_TEST_ASSETS", str(tmp_path / "assets"))
    import importlib

    import sync_assets

    importlib.reload(sync_assets)
    assets = tmp_path / "assets"
    sync_assets.sync(assets)
    (assets / "__init__.py").unlink()
    with pytest.raises(RuntimeError, match="missing"):
        sync_assets._verify_bundle(assets)
    (assets / "__init__.py").write_text(
        '"""Generated runtime asset bundle."""\n', encoding="utf-8"
    )
    # restore exact original bytes via re-sync, then add an extra executable
    sync_assets.sync(assets)
    (assets / "schemas" / "extra.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="extra packaged file"):
        sync_assets._verify_bundle(assets)
    (assets / "schemas" / "extra.sh").unlink()


# ------------------------------------------------------ link/reparse matrix


def _make_link(target: Path, link: Path) -> None:
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link,
                   target_is_directory=target.is_dir())


def test_junction_inside_bundle_rejected(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    monkeypatch.setenv("DELTAFUSE_TEST_REPO", str(_make_repo(tmp_path)))
    monkeypatch.setenv("DELTAFUSE_TEST_ASSETS", str(tmp_path / "assets"))
    import importlib

    import sync_assets

    importlib.reload(sync_assets)
    assets = tmp_path / "assets"
    sync_assets.sync(assets)
    outside = tmp_path / "outside-secret"
    outside.mkdir()
    _make_link(outside, assets / "schemas" / "link")
    with pytest.raises(RuntimeError, match="symlink/junction"):
        sync_assets._verify_bundle(assets)


def test_broken_link_inside_bundle_rejected(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    monkeypatch.setenv("DELTAFUSE_TEST_REPO", str(_make_repo(tmp_path)))
    monkeypatch.setenv("DELTAFUSE_TEST_ASSETS", str(tmp_path / "assets"))
    import importlib

    import sync_assets

    importlib.reload(sync_assets)
    assets = tmp_path / "assets"
    sync_assets.sync(assets)
    # Windows junctions cannot dangle: create the junction, then remove the
    # target so the link is broken
    gone = tmp_path / "vanishing-target"
    gone.mkdir()
    _make_link(gone, assets / "templates" / "broken")
    import shutil as _shutil

    _shutil.rmtree(gone)
    with pytest.raises(RuntimeError, match="symlink/junction"):
        sync_assets._verify_bundle(assets)


def test_check_rejects_reparse_in_committed_bundle(tmp_path):
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    assert _run(repo, assets).returncode == 0
    _make_link(repo / "process", assets / "skills" / "jump")
    proc = _run(repo, assets, "--check")
    assert proc.returncode != 0, proc.stdout
    assert "symlink/junction" in (proc.stdout + proc.stderr)


# --------------------------------------------------- recovery interactions


def test_recovery_commits_verified_next_when_prev_tampered(tmp_path):
    """A crash copy whose __init__.py was swapped is invalid; recovery must
    land on the fully verified copy, never the tampered one."""
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    assert _run(repo, assets).returncode == 0
    env = {
        **os.environ,
        "DELTAFUSE_TEST_REPO": str(repo),
        "DELTAFUSE_TEST_ASSETS": str(assets),
        "DELTAFUSE_SYNC_CRASH_AT": "prev-moved",
    }
    for name in BUNDLE_ROOTS:
        (repo / "process" / name / "a.txt").write_text(
            f"{name}-v2", encoding="utf-8"
        )
    killed = subprocess.run(
        [sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True,
        timeout=120,
    )
    assert killed.returncode != 0
    prev = next(assets.parent.glob("assets.prev-*"))
    (prev / "__init__.py").write_text("evil", encoding="utf-8")
    env.pop("DELTAFUSE_SYNC_CRASH_AT")
    rec = subprocess.run(
        [sys.executable, str(SCRIPT), "--recover-only"], env=env,
        capture_output=True, text=True, timeout=120,
    )
    assert rec.returncode == 0, rec.stderr + rec.stdout
    tree = _tree_hash(assets)
    assert tree["__init__.py"] == hashlib.sha256(
        b'"""Generated runtime asset bundle. DO NOT EDIT: run scripts/sync_assets.py."""\n'
    ).hexdigest()
    for name in BUNDLE_ROOTS:
        assert tree[f"{name}/a.txt"] == hashlib.sha256(
            f"{name}-v2".encode()
        ).hexdigest()


def test_ambiguous_state_deletes_nothing(tmp_path):
    repo = _make_repo(tmp_path)
    assets = tmp_path / "assets"
    assert _run(repo, assets).returncode == 0
    v1 = _tree_hash(assets)
    env = {
        **os.environ,
        "DELTAFUSE_TEST_REPO": str(repo),
        "DELTAFUSE_TEST_ASSETS": str(assets),
        "DELTAFUSE_SYNC_CRASH_AT": "prev-moved",
    }
    for name in BUNDLE_ROOTS:
        (repo / "process" / name / "a.txt").write_text(
            f"{name}-v2", encoding="utf-8"
        )
    assert subprocess.run([sys.executable, str(SCRIPT)], env=env,
                          capture_output=True, timeout=120).returncode != 0
    prev = next(assets.parent.glob("assets.prev-*"))
    nxt = next(assets.parent.glob("assets.next-*"))
    (prev / "__init__.py").write_text("evil", encoding="utf-8")
    (nxt / "__init__.py").write_text("evil", encoding="utf-8")
    env.pop("DELTAFUSE_SYNC_CRASH_AT")
    rec = subprocess.run(
        [sys.executable, str(SCRIPT), "--recover-only"], env=env,
        capture_output=True, text=True, timeout=120,
    )
    assert rec.returncode != 0  # ambiguous: stop WITHOUT deletion
    assert _tree_hash(prev) != {}
    assert (prev / "__init__.py").read_text(encoding="utf-8") == "evil"
    assert assets.exists() is False or _tree_hash(assets) in (v1, {})
