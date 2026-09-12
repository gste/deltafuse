"""QF-004 integration: staging-root boundary for Worker command execution."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys = pytest.importorskip("sys")
sys.path.insert(0, "scripts")

import qualify  # noqa: E402
from qualify_staging import StagingRoot  # noqa: E402


def _scripted_turns(script):
    state = {"n": 0}

    def fake_turn(base_url, model, messages):
        content = script[min(state["n"], len(script) - 1)]
        state["n"] += 1
        return {"content": content, "prompt_tokens": 100}

    return fake_turn


def _ok_envelope(monkeypatch):
    from deltafuse import cli as cli_mod

    monkeypatch.setattr(
        cli_mod, "main",
        lambda argv: print(json.dumps({"envelope": {"write": ["docs/**", "**"]}})) or 0,
    )


def test_worker_python_cannot_read_judge_pack(tmp_path, monkeypatch):
    """A Worker-authored test running through the real staging mechanism
    cannot find the judge pack: it is physically absent from staging and no
    framework env vars are passed."""
    _ok_envelope(monkeypatch)
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    staging = StagingRoot.create(tmp_path / "staging", build_venv=False)
    work = staging.new_workdir("run1", sandbox)
    qualify.init_sandbox_git(work)
    (work / "pack_probe_test.py").write_text(
        "from pathlib import Path\n\n"
        "def test_judge_pack_absent():\n"
        "    assert not Path('process/bench/cases').exists()\n"
        "    assert not Path('../../process').exists()\n",
        encoding="utf-8",
    )
    io = qualify.SandboxIO(work)
    io.write_envelope = qualify.EnvelopeState("ok", ["**"])
    io.exec_env = staging.env(framework_root=tmp_path)
    io.interpreter = staging.interpreter()
    result = io.shell("python -m pytest -q pack_probe_test.py")
    assert result.startswith("exit=0"), result
    assert not (staging.base / "process").exists()
    assert not (work / "process").exists()


def test_staging_escape_via_drive_worker(tmp_path, monkeypatch):
    """A shell command that drops a file into staging outside the work dir is
    detected by the walker and counted as a T7 violation."""
    _ok_envelope(monkeypatch)
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    staging = StagingRoot.create(tmp_path / "staging", build_venv=False)
    work = staging.new_workdir("run1", sandbox)
    # the Worker-authored command itself cannot escape by policy; simulate a
    # process writing outside the work dir by a helper executed by the stub
    real_shell = qualify.SandboxIO.shell

    def escape_shell(self, command, timeout=300):
        if command == "git status":
            return real_shell(self, command, timeout=timeout)
        (staging.base / "leak.txt").write_text("x", encoding="utf-8")
        return "exit=0\n"

    monkeypatch.setattr(qualify.SandboxIO, "shell", escape_shell)
    monkeypatch.setattr(
        qualify, "worker_turn",
        _scripted_turns([
            '{"tool": "shell", "command": "deltafuse advance"}',
            '{"tool": "shell", "command": "git status"}',
            '{"tool": "done", "reason": "ok"}',
        ]),
    )
    metrics = qualify.drive_worker(work, "http://x", "m", "case", "system", staging=staging)
    assert metrics["t7_breakdown"]["staging_escape"] >= 1
    assert metrics["envelope_violations"] >= 1
