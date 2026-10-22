"""`deltafuse evidence` finds the runner a Worker names the way a shell would.

Fuse-Back on J01 (2026-10-08, Windows 11, Maven 3.9.12): `-- mvn -B test` ran nothing - Maven on
Windows is `mvn.cmd`, and CreateProcess does not look for it by the bare name - so Red was
recorded `fixture-error` with `[WinError 2]`, although `mvn` is the runner `workflow.test_commands`
and the skills name. Writing `mvn.cmd` in the product would break Linux and CI. The Core now
resolves the program through `shutil.which` (PATHEXT on Windows) and keeps the Worker's argv in
the record; a runner found nowhere is named in the record.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from deltafuse.core import evidence
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder


def _decomposed(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return MockChangeBuilder(tmp_path, change_id="CHG-200", title="JVM runner").step_through_decompose()


REAL_RUN = subprocess.run


def _capture_runs(monkeypatch) -> list[list[str]]:
    """Test commands are captured; the Core's own git calls run for real."""
    launched: list[list[str]] = []

    def fake_run(argv, **kwargs):
        if argv and argv[0] == "git":
            return REAL_RUN(argv, **kwargs)
        launched.append(list(argv))
        return subprocess.CompletedProcess(argv, 1, stdout="Tests run: 1, Failures: 1\nAssertionError", stderr="")

    monkeypatch.setattr(evidence.subprocess, "run", fake_run)
    return launched


def test_windows_runs_the_resolved_runner_and_records_the_workers_command(
    tmp_path: Path, repo_root: Path, monkeypatch
):
    builder = _decomposed(tmp_path, repo_root)
    launched = _capture_runs(monkeypatch)
    monkeypatch.setattr(evidence, "_on_windows", lambda: True)
    monkeypatch.setattr(
        evidence.shutil, "which", lambda name, path=None: r"C:\tools\maven\bin\mvn.cmd" if name == "mvn" else None
    )
    outcome = evidence.run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=["mvn", "-B", "test"])
    assert launched == [[r"C:\tools\maven\bin\mvn.cmd", "-B", "test"]]
    assert outcome.payload["command"] == "mvn -B test"


def test_a_runner_found_nowhere_is_named_not_winerror(tmp_path: Path, repo_root: Path, monkeypatch):
    """Not found by `which`, the argv still runs as given (CreateProcess may know more, e.g. the
    venv's own directory); when that fails too, the record names the runner."""
    builder = _decomposed(tmp_path, repo_root)
    launched: list[list[str]] = []

    def missing(argv, **kwargs):
        if argv and argv[0] == "git":
            return REAL_RUN(argv, **kwargs)
        launched.append(list(argv))
        raise FileNotFoundError(2, "[WinError 2] The system cannot find the file specified")

    monkeypatch.setattr(evidence.subprocess, "run", missing)
    monkeypatch.setattr(evidence, "_on_windows", lambda: True)
    monkeypatch.setattr(evidence.shutil, "which", lambda name, path=None: None)
    outcome = evidence.run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=["mvn", "-B", "test"])
    assert launched == [["mvn", "-B", "test"]]
    assert outcome.payload["exit_code"] == 127
    assert "runner `mvn` not found on PATH" in outcome.payload["summary"]


def test_an_executable_runner_is_left_to_createprocess(tmp_path: Path, monkeypatch):
    """`python` resolved through PATH could be another interpreter than the venv's own."""
    monkeypatch.setattr(evidence, "_on_windows", lambda: True)
    monkeypatch.setattr(evidence.shutil, "which", lambda name, path=None: r"C:\Python\python.exe")
    assert evidence.resolve_runner(["python", "-m", "pytest"], tmp_path) == ["python", "-m", "pytest"]


def test_off_windows_the_argv_is_run_as_given(tmp_path: Path, repo_root: Path, monkeypatch):
    builder = _decomposed(tmp_path, repo_root)
    launched = _capture_runs(monkeypatch)
    monkeypatch.setattr(evidence, "_on_windows", lambda: False)
    monkeypatch.setattr(evidence.shutil, "which", lambda name, path=None: "/usr/bin/mvn")
    evidence.run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=["mvn", "-B", "test"])
    assert launched == [["mvn", "-B", "test"]]


@pytest.mark.parametrize("argument", ["test&calc", "a|b", "x>out", "^x", "%PATH%"])
def test_a_batch_runner_refuses_arguments_cmd_would_read(tmp_path: Path, repo_root: Path, monkeypatch, argument):
    """`mvn.cmd` runs through cmd.exe, which reads & | < > ^ % in its arguments as its own."""
    builder = _decomposed(tmp_path, repo_root)
    launched = _capture_runs(monkeypatch)
    monkeypatch.setattr(evidence, "_on_windows", lambda: True)
    monkeypatch.setattr(evidence.shutil, "which", lambda name, path=None: r"C:\tools\mvn.cmd")
    with pytest.raises(evidence.EvidenceRunError, match="cmd.exe"):
        evidence.run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=["mvn", argument])
    assert launched == []


def test_a_relative_runner_resolves_against_the_product(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(evidence, "_on_windows", lambda: True)
    seen: list[str] = []

    def which(name, path=None):
        seen.append(name)
        return name + ".bat"

    monkeypatch.setattr(evidence.shutil, "which", which)
    assert evidence.resolve_runner(["./gradlew", "test"], tmp_path) == [str(tmp_path / "gradlew") + ".bat", "test"]
    assert seen == [str(tmp_path / "gradlew")]
