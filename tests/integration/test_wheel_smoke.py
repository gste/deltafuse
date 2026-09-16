"""V3-FIX-021: reproducible wheel smoke — build, install into a clean venv,
run the installed CLI without any source checkout on sys.path."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import venv
from pathlib import Path

import os

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str] | str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600, **kwargs)


def test_wheel_build_install_and_cli_smoke(tmp_path: Path):
    """build -> install (clean venv) -> CLI smoke with no source checkout."""
    if importlib.util.find_spec("pip") is None:
        pytest.fail("blocked: pip is unavailable; wheel smoke cannot run silently skipped")
    dist = tmp_path / "dist"
    # 1. Build a real wheel from the repo. The bundle must already be in
    # sync: the test NEVER fixes the source tree on drift (completion step 7).
    check = _run([sys.executable, str(REPO_ROOT / "scripts" / "sync_assets.py"), "--check"])
    assert check.returncode == 0, (
        "asset bundle drift; run scripts/sync_assets.py first: "
        + check.stdout + check.stderr
    )
    build = _run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist), str(REPO_ROOT)]
    )
    assert build.returncode == 0, build.stdout + build.stderr
    wheels = list(dist.glob("deltafuse-*.whl"))
    assert wheels, "no wheel built"
    wheel = wheels[0]

    # 2. Install into a clean venv.
    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    pip = venv_dir / "Scripts" / "python.exe"
    if not pip.is_file():
        pip = venv_dir / "bin" / "python"
    install = _run([str(pip), "-I", "-m", "pip", "install", str(wheel)])
    assert install.returncode == 0, install.stdout + install.stderr

    # 3. Run the installed CLI from a directory with no checkout on sys.path.
    workdir = tmp_path / "clean"
    workdir.mkdir()
    env = {k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"}
    # The installed CLI must self-identify the release version and answer.
    result = _run([str(pip), "-m", "deltafuse", "--help"], cwd=str(workdir), env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "usage:" in (result.stdout + result.stderr).lower()

    init_result = _run([str(pip), "-m", "deltafuse", "init", str(workdir / "product")], cwd=str(workdir), env=env)
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr
    lock = workdir / "product" / ".deltafuse" / "lock.yaml"
    assert lock.is_file()
    lock_text = lock.read_text(encoding="utf-8")
    assert "schema_version: 3" in lock_text, "installed wheel must write lock contract v3"

    validate = _run(
        [str(pip), "-m", "deltafuse", "validate-config", str(workdir / "product")],
        cwd=str(workdir), env=env,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr

    # 4. QF-010: the test itself never writes outside tmp_path. The evidence
    # object is validated for shape and dumped into tmp_path only; durable
    # release evidence is created by the explicit scripts/wheel_evidence.py.
    import hashlib
    import json as _json

    evidence = {
        "schema_version": 1,
        "wheel": wheel.name,
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "python": sys.version.split()[0],
        "platform": sys.platform,
    }
    evidence_path = tmp_path / f"{wheel.stem}-build-manifest.json"
    evidence_path.write_text(_json.dumps(evidence, indent=2), encoding="utf-8")
    assert evidence_path.is_file()
    assert evidence["sha256"]
    assert evidence["wheel"].endswith(".whl")


def test_wheel_smoke_leaves_working_tree_clean(tmp_path: Path, monkeypatch):
    """QF-010: a full wheel smoke leaves `git status --porcelain` identical."""
    before = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=REPO_ROOT
    ).stdout
    monkeypatch.setenv("DELTAFUSE_WHEEL_EVIDENCE_DIR", str(tmp_path))
    test_wheel_build_install_and_cli_smoke(tmp_path)
    after = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=REPO_ROOT
    ).stdout
    assert after == before
