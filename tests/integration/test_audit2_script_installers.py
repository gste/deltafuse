"""Audit 2026-11-17 (df-leash): the script installers. FW-5 (init.ps1 resolved a relative target
against the process directory, not PowerShell's location - it installed a product scaffold into
the framework checkout during the audit), FW-19 (init.sh wrote no .gitignore; init.ps1 glued its
first entry onto the last line of an existing one).

Every target here is an absolute path under pytest's tmp_path, and the process directory is too.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.fixtures.leash_walk import REPO_ROOT, env

# B-12 (audit 3): the per-clone bookkeeping is ignored too.
ENTRIES = [".deltafuse/hooks/", ".deltafuse/tmp/", ".deltafuse/journal/", ".agents/skills/", ".cursor/skills/", ".gemini/skills/"]
PWSH = shutil.which("pwsh") or shutil.which("powershell")
BASH = shutil.which("bash")


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    assert REPO_ROOT not in (cwd, *cwd.parents), "never run an installer from the framework checkout"
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env())


def _ps1(cwd: Path, command: str) -> subprocess.CompletedProcess:
    if PWSH is None:
        pytest.skip("no PowerShell")
    return _run([PWSH, "-NoProfile", "-Command", command], cwd)


def _sh(target: Path) -> subprocess.CompletedProcess:
    if BASH is None:
        pytest.skip("no bash")
    return _run([BASH, (REPO_ROOT / "scripts" / "init.sh").as_posix(), target.as_posix()], target.parent)


def _lines(path: Path) -> list[str]:
    data = path.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf"), "a BOM makes the first .gitignore line match nothing"
    return data.decode("utf-8").splitlines()


# --- FW-5 -------------------------------------------------------------------------------

@pytest.mark.parametrize("argument", ["", " .", " sub"])
def test_init_ps1_resolves_a_relative_target_against_the_powershell_location(tmp_path, argument):
    started = tmp_path / "started-here"
    went = tmp_path / "went-here"
    started.mkdir()
    went.mkdir()
    script = REPO_ROOT / "scripts" / "init.ps1"
    proc = _ps1(started, f"Set-Location -LiteralPath '{went}'; & '{script}'{argument}; exit $LASTEXITCODE")
    target = went / "sub" if argument.strip() == "sub" else went
    assert (target / ".deltafuse" / "lock.yaml").is_file(), proc.stdout + proc.stderr
    assert list(started.iterdir()) == [], "installed into the directory the process started in"


def test_init_ps1_takes_an_absolute_target_from_anywhere(tmp_path):
    started = tmp_path / "started-here"
    target = tmp_path / "product"
    started.mkdir()
    script = REPO_ROOT / "scripts" / "init.ps1"
    proc = _ps1(started, f"& '{script}' '{target}'; exit $LASTEXITCODE")
    assert (target / ".deltafuse" / "lock.yaml").is_file(), proc.stdout + proc.stderr
    assert list(started.iterdir()) == []


# --- FW-19 ------------------------------------------------------------------------------

def test_init_sh_writes_the_gitignore(tmp_path):
    target = tmp_path / "product"
    target.mkdir()
    proc = _sh(target)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert [line for line in _lines(target / ".gitignore") if line] == ENTRIES


@pytest.mark.parametrize("installer", ["sh", "ps1", "python"])
@pytest.mark.parametrize("ending", ["", "\n"])
def test_an_existing_gitignore_keeps_its_last_line(tmp_path, installer, ending):
    """init.ps1 wrote `node_modules/.deltafuse/hooks/` and the rest of its entries on that one line."""
    target = tmp_path / "product"
    target.mkdir()
    (target / ".gitignore").write_bytes(("*.log\nnode_modules/" + ending).encode())
    for _ in range(2):  # the second run adds nothing
        if installer == "sh":
            proc = _sh(target)
        elif installer == "ps1":
            proc = _ps1(tmp_path, f"& '{REPO_ROOT / 'scripts' / 'init.ps1'}' '{target}'; exit $LASTEXITCODE")
        else:
            from deltafuse.core.installer import install

            install(target_dir=target, framework_root=REPO_ROOT)
            proc = None
        assert proc is None or proc.returncode == 0, proc.stdout + proc.stderr
    assert [line for line in _lines(target / ".gitignore") if line] == ["*.log", "node_modules/", *ENTRIES]
