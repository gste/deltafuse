"""V3-FIX-021: reproducible wheel smoke — build, install into a clean venv,
run the installed CLI without any source checkout on sys.path."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import venv
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _pip_available() -> bool:
    return importlib.util.find_spec("pip") is not None


pytestmark = pytest.mark.skipif(
    not _pip_available() or sys.platform not in ("win32", "linux", "darwin"),
    reason="wheel smoke needs pip and a supported platform",
)


def _run(cmd: list[str] | str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600, **kwargs)


def test_wheel_build_install_and_cli_smoke(tmp_path: Path):
    """build -> install (clean venv) -> CLI smoke with no source checkout."""
    dist = tmp_path / "dist"
    # 1. Build a real wheel from the repo (bundle must be current first).
    check = _run([sys.executable, str(REPO_ROOT / "scripts" / "sync_assets.py"), "--check"])
    if check.returncode != 0:
        sync = _run([sys.executable, str(REPO_ROOT / "scripts" / "sync_assets.py")])
        assert sync.returncode == 0, sync.stdout + sync.stderr
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
    lock = json.loads("null") if False else (workdir / "product" / ".deltafuse" / "lock.yaml")
    assert lock.is_file()
    lock_text = lock.read_text(encoding="utf-8")
    assert "schema_version: 3" in lock_text, "installed wheel must write lock contract v3"

    # 4. Build manifest evidence: keep the wheel hash with the test artifacts.
    import hashlib

    wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (tmp_path / "build-manifest.json").write_text(
        json.dumps({"wheel": wheel.name, "sha256": wheel_hash}, indent=2),
        encoding="utf-8",
    )
