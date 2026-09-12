"""QF-004/QF-013: staging root for local-dev Worker command execution.

L1 staging is a LOCAL-DEV helper only (`--executor local-dev`); it does not
isolate Worker-authored code from the host filesystem and its artifacts are
capped at the ``non-release`` verdict (QF-013). Release campaigns run the
Worker inside the isolated boundary (``scripts/qualify_executor.py``).

The qualification Worker never runs commands inside the framework repository.
The judge side prepares a staging directory once per campaign:

    <staging>/
      venv/            # optional clean venv (wheel deltafuse + pytest, no pack)
      work/<run_id>/   # per-run copy of the sandbox git repository

Guarantees enforced here (see backlog/product/v3/qualification-threat-model.md):

- the judge pack (`process/bench/cases/**`) is never copied into staging;
- Worker commands run with a minimal environment (no PYTHON* variables, no
  framework environment references) and a PATH that resolves to the controlled
  interpreter first;
- a walker diffs the staging tree (excluding venv and work) around every
  command, so any file appearing outside the work dir is reported as
  `staging_escape` (a T7 violation).

OS-level isolation (container/VM) is an L2 option documented in the threat
model; L1 (this module) guarantees the pack is absent and changes are
attributed, not that Worker code is sandboxed against the host kernel.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# QF-005: the command environment is built from scratch; nothing is inherited
# from the judge process (see StagingRoot.env).


class StagingRoot:
    """Judge-side staging directory with per-run work copies and a walker."""

    def __init__(self, base: Path, venv_dir: Path | None, work_root: Path):
        self.base = base
        self.venv_dir = venv_dir
        self.work_root = work_root

    @classmethod
    def create(cls, base: Path, build_venv: bool = False, framework_root: Path | None = None) -> "StagingRoot":
        base = Path(base)
        base.mkdir(parents=True, exist_ok=True)
        venv_dir: Path | None = None
        if build_venv:
            if framework_root is None:
                raise ValueError("build_venv=True requires framework_root")
            venv_dir = base / "venv"
            _build_venv(venv_dir, framework_root, base / "wheels")
        return cls(base, venv_dir, base / "work")

    def interpreter(self) -> str:
        """Controlled interpreter: the staging venv python when present,
        otherwise the runner's own interpreter (pinned properly by QF-005)."""
        if self.venv_dir is not None and self.venv_dir.exists():
            exe = (
                self.venv_dir / "Scripts" / "python.exe"
                if os.name == "nt"
                else self.venv_dir / "bin" / "python"
            )
            if exe.exists():
                return str(exe)
        return sys.executable

    def env(self, framework_root: Path | None = None) -> dict[str, str]:
        """QF-005: command environment built from scratch (allowlist).

        PATH resolves to the controlled interpreter dir and git first; no
        PYTEST_*/PYTHON*/framework variables are passed. TEMP/TMP (Windows)
        and HOME/TMPDIR (POSIX) are redirected into the staging tree.
        """
        path_parts = [str(Path(self.interpreter()).parent)]
        git = shutil.which("git")
        if git:
            path_parts.append(str(Path(git).parent))
        tmp_dir = self.base / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
            path_parts.append(os.path.join(system_root, "System32"))
            env: dict[str, str] = {
                "PATH": os.pathsep.join(dict.fromkeys(path_parts)),
                "SYSTEMROOT": system_root,
                "SYSTEMDRIVE": os.environ.get("SYSTEMDRIVE", "C:"),
                "COMSPEC": os.environ.get("COMSPEC", os.path.join(system_root, "System32", "cmd.exe")),
                "PATHEXT": ".COM;.EXE;.BAT;.CMD",
                "TEMP": str(tmp_dir),
                "TMP": str(tmp_dir),
            }
        else:
            home_dir = self.base / "home"
            home_dir.mkdir(parents=True, exist_ok=True)
            path_parts += ["/usr/bin", "/bin"]
            env = {
                "PATH": os.pathsep.join(dict.fromkeys(path_parts)),
                "HOME": str(home_dir),
                "TMPDIR": str(tmp_dir),
            }
        if framework_root is not None:
            # defensive: no value may reference the framework root
            env = {k: v for k, v in env.items() if str(framework_root) not in v}
        return env

    def new_workdir(self, run_id: str, sandbox: Path) -> Path:
        """Clean per-run copy of the sandbox git repository."""
        work = self.work_root / run_id
        if work.exists():
            shutil.rmtree(work)
        work.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(sandbox, work)
        return work

    def collect_workdir(self, run_id: str, sandbox: Path) -> None:
        """Judge side: move the (mutated) work dir back over the sandbox."""
        work = self.work_root / run_id
        if sandbox.exists():
            shutil.rmtree(sandbox)
        shutil.copytree(work, sandbox)

    def _walk(self) -> set[str]:
        """Relative posix paths of every file in staging, excluding venv and
        work copies (they are the sanctioned writable roots)."""
        found: set[str] = set()
        for root, dirs, files in os.walk(self.base):
            root_path = Path(root)
            if self.venv_dir is not None and root_path == self.venv_dir:
                dirs[:] = []
                continue
            if root_path == self.work_root:
                dirs[:] = []
                continue
            for name in files:
                found.add(root_path.joinpath(name).relative_to(self.base).as_posix())
        return found

    def escape_walker(self):
        """Returns a check() callable: new paths outside work/venv since the
        previous call (call it around each Worker command)."""
        seen = self._walk()

        def check() -> list[str]:
            nonlocal seen
            current = self._walk()
            escaped = sorted(current - seen)
            seen = current
            return escaped

        return check

    def teardown(self) -> None:
        shutil.rmtree(self.base, ignore_errors=True)


def _build_venv(venv_dir: Path, framework_root: Path, wheels_dir: Path) -> None:
    """Build a clean venv with the framework wheel + pytest and nothing else.

    Executed explicitly on the qualification host (one venv per campaign);
    requires a reachable package index for pytest (the framework itself is
    built locally with `pip wheel --no-deps` from the clean tree).
    """
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    py = (
        venv_dir / "Scripts" / "python.exe"
        if os.name == "nt"
        else venv_dir / "bin" / "python"
    )
    wheels_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(wheels_dir), str(framework_root)],
        check=True,
    )
    subprocess.run([str(py), "-m", "pip", "install", str(framework_root), "pytest"], check=True)
