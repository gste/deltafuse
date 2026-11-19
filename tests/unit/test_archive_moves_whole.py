"""Audit 2026-11, FL-15 and FL-14: archive moves the package in one step, and its intake with it.

FL-15: `deltafuse archive .` run from inside the Change directory on Windows exited 2
(WinError 32) with the package copied to the archive and an empty `docs/changes/<id>/` left.
FL-14: docs/workflow.md says archiving moves the Change's intake sources to
`docs/archive/intake/`; nothing did.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from deltafuse.core import archiver
from deltafuse.core.archiver import ArchivalError, archive_change
from deltafuse.core.decide import apply_decision
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, intake_sources_pending
from deltafuse.core.transitions import receipt_chain_errors
from tests.fixtures.change_builder import MockChangeBuilder


def _converged(tmp_path: Path, repo_root: Path, cid: str, intake_refs: list[str] | None = None) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=cid, title="Arch").step_intake()
    if intake_refs is not None:
        builder._update_change_yaml({"source": {"request": "request.md", "intake_refs": intake_refs}})
    return builder.step_analyze().step_specify().step_decompose().step_declare().step_implement().step_verify()


def _archives(product: Path) -> list[Path]:
    return [p for p in (product / "docs" / "archive" / "changes").iterdir() if p.is_dir()]


def test_archive_from_inside_the_change_directory(tmp_path: Path, repo_root: Path, monkeypatch):
    """The Core leaves the directory itself before the move, so its own working directory does
    not hold the package.

    Audit 3 (B's suite run): this test ran `python -m deltafuse archive .` as a child process
    whose working directory was the Change, and failed with WinError 32 under a virtualenv. On
    Windows a venv's `python.exe` is a launcher that starts the real interpreter as a child: the
    launcher keeps the Change as its working directory, and the Core's `chdir` cannot move it. It
    passed where `sys.executable` is the interpreter itself. Here the Core runs in this process,
    whatever launched pytest, so the test asks only what the Core controls."""
    builder = _converged(tmp_path, repo_root, "CHG-830")
    monkeypatch.chdir(builder.change_dir)
    archive_change(Path("."), repo_root=tmp_path)
    assert Path.cwd().resolve() == tmp_path.resolve()
    assert not builder.change_dir.exists()
    (archived,) = _archives(tmp_path)
    assert yaml.safe_load((archived / "change.yaml").read_text(encoding="utf-8"))["status"] == "archived"
    assert not build_work_queue(tmp_path).blocked


def test_a_shell_inside_the_change_directory_holds_it_on_windows(tmp_path: Path, repo_root: Path):
    """The twin, and the environment that made the test above flaky: another process - a shell, a
    venv launcher - whose working directory is the Change. Windows refuses the rename; the Core
    moves nothing and says to leave the directory, as its message promises. POSIX renames it."""
    builder = _converged(tmp_path, repo_root, "CHG-832")
    env = dict(os.environ, PYTHONPATH=str(repo_root / "src"), PYTHONIOENCODING="utf-8")
    command = [sys.executable, "-m", "deltafuse", "archive", "."]
    if os.name == "nt":
        shell = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", subprocess.list2cmdline(command)]
    else:
        shell = ["sh", "-c", " ".join(f"'{part}'" for part in command)]
    proc = subprocess.run(shell, cwd=str(builder.change_dir), env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    if os.name != "nt":
        assert proc.returncode == 0, proc.stderr
        assert not builder.change_dir.exists()
        return
    assert proc.returncode != 0
    assert "nothing was archived" in proc.stderr and "leave it in every shell" in proc.stderr, proc.stderr
    assert (builder.change_dir / "change.yaml").is_file() and _archives(tmp_path) == []
    assert yaml.safe_load((builder.change_dir / "change.yaml").read_text(encoding="utf-8"))["status"] == "converged"
    # ... and from the product root it goes through.
    assert archive_change(builder.change_dir, repo_root=tmp_path).is_dir() and not builder.change_dir.exists()


def test_a_move_that_fails_archives_nothing(tmp_path: Path, repo_root: Path, monkeypatch):
    """The nearest bypass: the directory is held by another process, which leaving it ourselves
    does not cure. Nothing may be half done - no copy, no `archived` status, no empty folder."""
    builder = _converged(tmp_path, repo_root, "CHG-831")
    change = builder.change_dir
    before = sorted(p.relative_to(change).as_posix() for p in change.rglob("*"))

    def held(src, dst):
        raise PermissionError(32, "The process cannot access the file because it is being used by another process")

    monkeypatch.setattr(archiver.os, "rename", held)
    with pytest.raises(ArchivalError, match="nothing was archived"):
        archive_change(change, repo_root=tmp_path)
    monkeypatch.undo()

    assert sorted(p.relative_to(change).as_posix() for p in change.rglob("*")) == before
    assert yaml.safe_load((change / "change.yaml").read_text(encoding="utf-8"))["status"] == "converged"
    assert _archives(tmp_path) == []
    assert receipt_chain_errors(tmp_path, change) == []
    assert not build_work_queue(tmp_path).blocked
    # ... and the second attempt goes through.
    assert archive_change(change, repo_root=tmp_path).is_dir() and not change.exists()


def test_archive_moves_the_intake_sources_the_change_took_in(tmp_path: Path, repo_root: Path):
    intake = tmp_path / "docs" / "intake"
    intake.mkdir(parents=True, exist_ok=True)
    (intake / "banner-request.md").write_text("Please print a banner.\n", encoding="utf-8")
    (intake / "other.md").write_text("Something else.\n", encoding="utf-8")
    builder = _converged(tmp_path, repo_root, "CHG-832", ["docs/intake/banner-request.md"])

    archive_change(builder.change_dir, repo_root=tmp_path)
    assert not (intake / "banner-request.md").exists()
    assert (tmp_path / "docs" / "archive" / "intake" / "banner-request.md").read_text(encoding="utf-8") == "Please print a banner.\n"
    assert (intake / "other.md").is_file()  # not this Change's
    assert intake_sources_pending(tmp_path)  # other.md still waits; the archived one does not


def test_archive_moves_only_what_lies_under_docs_intake_and_never_overwrites(tmp_path: Path, repo_root: Path):
    """The bypasses of "move what intake_refs names": a reference that climbs out of
    docs/intake, one another active Change still cites, and a name already archived."""
    intake = tmp_path / "docs" / "intake"
    intake.mkdir(parents=True, exist_ok=True)
    for name in ("shared.md", "taken.md"):
        (intake / name).write_text(name, encoding="utf-8")
    refs = ["docs/intake/../../.deltafuse/lock.yaml", "docs/intake/shared.md", "docs/intake/taken.md", "docs/intake"]
    builder = _converged(tmp_path, repo_root, "CHG-833", refs)
    other = MockChangeBuilder(tmp_path, change_id="CHG-834", title="Other").step_intake()
    other._update_change_yaml({"source": {"request": "request.md", "intake_refs": ["docs/intake/shared.md"]}})
    archived_intake = tmp_path / "docs" / "archive" / "intake"
    archived_intake.mkdir(parents=True, exist_ok=True)
    (archived_intake / "taken.md").write_text("an earlier record", encoding="utf-8")

    archive_change(builder.change_dir, repo_root=tmp_path)
    assert (tmp_path / ".deltafuse" / "lock.yaml").is_file()
    assert (intake / "shared.md").is_file()
    assert (intake / "taken.md").is_file()
    assert (archived_intake / "taken.md").read_text(encoding="utf-8") == "an earlier record"
    assert intake.is_dir()


def test_a_closed_change_takes_its_intake_along_too(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    intake = tmp_path / "docs" / "intake"
    intake.mkdir(parents=True, exist_ok=True)
    (intake / "note.md").write_text("note", encoding="utf-8")
    builder = MockChangeBuilder(tmp_path, change_id="CHG-835", title="No").step_intake()
    builder._update_change_yaml({"source": {"request": "request.md", "intake_refs": ["docs/intake/note.md"]}})
    builder.step_analyze()
    apply_decision(builder.change_dir, status="rejected", close=True, note="out of scope")
    archive_change(builder.change_dir, repo_root=tmp_path)
    assert not (intake / "note.md").exists()
    assert (tmp_path / "docs" / "archive" / "intake" / "note.md").is_file()
