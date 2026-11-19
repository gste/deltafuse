"""The pre-commit hook runs the interpreter that installed DeltaFuse (B-9, A-17).

Audit 3: the hook ran `${DELTAFUSE_PYTHON:-python}`, so the first commit of a product was judged
by another DeltaFuse, found through the system `python` on PATH ("needs one commit ... Make an
initial commit"), and an older install first on PATH judged several steps by accident.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from deltafuse.core.installer import install
from deltafuse.core.leash import HOOK_SCRIPT, hook_script

SH = shutil.which("sh") or shutil.which("bash")
REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=root, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", check=False)


def _product(tmp_path: Path) -> Path:
    root = tmp_path / "p"
    root.mkdir()
    _git(root, "init", "-q")
    install(target_dir=root, framework_root=REPO_ROOT)
    return root


def _hook(root: Path) -> Path:
    return root / ".git" / "hooks" / "pre-commit"


def _fake_python(tmp_path: Path, code: int) -> Path:
    """A `python` that is not DeltaFuse's: it exits with *code* whatever it is asked."""
    folder = tmp_path / f"fake{code}"
    folder.mkdir()
    fake = folder / "python"
    fake.write_text(f"#!/bin/sh\nexit {code}\n", encoding="utf-8", newline="\n")
    fake.chmod(0o755)
    return folder


def _run_hook(root: Path, hook: Path, *, path_first: Path, python_env: str | None) -> int:
    if SH is None:
        pytest.skip("no sh")
    env = dict(os.environ)
    env["PATH"] = str(path_first) + os.pathsep + env.get("PATH", "")
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT / "src"), str(REPO_ROOT)])
    env.pop("DELTAFUSE_PYTHON", None)
    if python_env is not None:
        env["DELTAFUSE_PYTHON"] = python_env
    return subprocess.run([SH, hook.as_posix()], cwd=root, env=env, capture_output=True, check=False).returncode


def test_init_writes_the_installing_interpreter_into_the_hook(tmp_path: Path):
    root = _product(tmp_path)
    text = _hook(root).read_text(encoding="utf-8")
    assert f"'{Path(sys.executable).as_posix()}'" in text
    assert text == hook_script(sys.executable)
    assert "python -m deltafuse" not in text.replace('"$py" -m deltafuse', "")


def test_the_hook_runs_the_recorded_interpreter_not_the_python_on_path(tmp_path: Path):
    root = _product(tmp_path)
    fake = _fake_python(tmp_path, 3)
    # The recorded interpreter runs `deltafuse leash`: the first commit is not judged, exit 0.
    assert _run_hook(root, _hook(root), path_first=fake, python_env=None) == 0


def test_deltafuse_python_overrides_the_recorded_interpreter(tmp_path: Path):
    root = _product(tmp_path)
    fake = _fake_python(tmp_path, 4)
    assert _run_hook(root, _hook(root), path_first=tmp_path, python_env=(fake / "python").as_posix()) == 4


def test_python_on_path_only_when_the_recorded_interpreter_is_gone(tmp_path: Path):
    """The twin path: a clone on another machine, where the recorded interpreter does not exist."""
    root = _product(tmp_path)
    gone = hook_script("C:/nowhere/python.exe" if os.name == "nt" else "/nowhere/python3")
    _hook(root).write_text(gone, encoding="utf-8", newline="\n")
    fake = _fake_python(tmp_path, 5)
    assert _run_hook(root, _hook(root), path_first=fake, python_env=None) == 5


def test_running_init_again_rewrites_the_recorded_interpreter(tmp_path: Path, monkeypatch):
    root = _product(tmp_path)
    other = tmp_path / "other machine python.exe"
    monkeypatch.setattr(sys, "executable", str(other))
    install(target_dir=root, framework_root=REPO_ROOT, force=True)
    assert f"'{other.as_posix()}'" in _hook(root).read_text(encoding="utf-8")
    assert f"'{other.as_posix()}'" in (root / ".deltafuse" / "hooks" / "pre-commit").read_text(encoding="utf-8")


def test_a_quote_in_the_path_stays_one_word():
    script = hook_script("C:/it's here/python.exe")
    assert "installed='C:/it'\\''s here/python.exe'" in script


def test_no_hook_file_is_tracked(tmp_path: Path):
    """The hooks live in .git/hooks and in the ignored .deltafuse/hooks/: a machine's path never
    reaches the repository."""
    root = _product(tmp_path)
    _git(root, "add", "-A")
    tracked = _git(root, "ls-files").stdout.splitlines()
    assert not [t for t in tracked if t.endswith("pre-commit")], tracked
    assert _git(root, "check-ignore", "-q", ".deltafuse/hooks/pre-commit").returncode == 0


def test_the_template_has_one_place_for_the_interpreter():
    assert HOOK_SCRIPT.count("@DELTAFUSE_PYTHON@") == 1


@pytest.mark.parametrize("installer", ["sh", "ps1"])
def test_the_script_installers_record_the_interpreter_too(tmp_path: Path, installer: str):
    """init.sh and init.ps1 write the same template with the interpreter they found
    (DELTAFUSE_PYTHON here, as the test environment sets it)."""
    from tests.integration.test_audit2_script_installers import _ps1, _sh

    target = tmp_path / "product"
    target.mkdir()
    if installer == "sh":
        proc = _sh(target)
    else:
        proc = _ps1(tmp_path, f"& '{REPO_ROOT / 'scripts' / 'init.ps1'}' '{target}'; exit $LASTEXITCODE")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = (target / ".deltafuse" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert text == hook_script(sys.executable), text
