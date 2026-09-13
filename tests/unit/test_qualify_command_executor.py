"""QF-019: judge-free command executor.

The Worker phase keeps model calls, tool orchestration, scoring and report
generation on the judge host; ONLY allowed Worker shell argv crosses into the
isolated command container (wheel DeltaFuse + pytest + git, sandbox-only
mount, cwd=/sandbox). The container never receives qualify.py, helper
modules, the bench pack or the framework checkout, and release shell commands
never execute through a local subprocess. Live-container checks live in
tests/integration/test_qual_command_container.py; everything here models the
runtime with a scripted fake runtime so Red/Green evidence does not need a
container daemon.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")

import qualify  # noqa: E402
import qualify_executor  # noqa: E402
from qualify_executor import (  # noqa: E402
    CommandResult,
    ContainerCommandExecutor,
    ExecutorError,
    ExecutorUnavailable,
    LocalCommandExecutor,
)

FAKE_IMAGE_ID = "sha256:" + "e" * 64


# ------------------------------------------------------------ fake runtime


HANDLER = r"""
import json, os, subprocess, sys, time

state_path = os.environ["FAKE_DOCKER_STATE"]
args = sys.argv[1:]

def load():
    with open(state_path, encoding="utf-8") as fh:
        return json.load(fh)

def save(state):
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)

state = load()
if args[0] == "run":
    state.setdefault("runs", []).append(args)
    save(state)
    print("fake-container-id-0001")
elif args[0] == "exec":
    state.setdefault("execs", []).append(args)
    save(state)
    mode = os.environ.get("FAKE_DOCKER_EXEC_MODE", "passthrough")
    if mode == "timeout":
        time.sleep(4)
    elif mode == "runtime-error":
        sys.stderr.write("docker: Error response from daemon: container is not running\n")
        sys.exit(125)
    elif mode == "exit3-malformed":
        sys.stdout.buffer.write(b"partial \xff output")
        sys.exit(3)
    elif mode == "container-exit4":
        sys.exit(4)
    else:
        cwd = state.get("sandbox") or os.getcwd()
        proc = subprocess.run(args[2:], cwd=cwd, capture_output=True, text=True)
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        sys.exit(proc.returncode)
elif args[0] == "stop":
    state.setdefault("stops", []).append(args)
    save(state)
elif args[:2] == ["image", "inspect"]:
    print(os.environ.get("FAKE_DOCKER_IMAGE_ID", "sha256:" + "e" * 64))
"""


def _write_fake_runtime(tmp_path: Path) -> str:
    handler = tmp_path / "fake_docker_handler.py"
    handler.write_text(HANDLER, encoding="utf-8")
    state = tmp_path / "fake_docker_state.json"
    state.write_text("{}", encoding="utf-8")
    if os.name == "nt":
        exe = tmp_path / "fake-docker.cmd"
        exe.write_text(
            f'@echo off\r\n"{sys.executable}" "{handler}" %*\r\n', encoding="utf-8"
        )
    else:
        exe = tmp_path / "fake-docker"
        exe.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{handler}" "$@"\n', encoding="utf-8"
        )
        exe.chmod(0o755)
    return str(exe)


@pytest.fixture()
def fake_runtime(tmp_path, monkeypatch):
    runtime = _write_fake_runtime(tmp_path)
    monkeypatch.setenv("FAKE_DOCKER_STATE", str(tmp_path / "fake_docker_state.json"))
    monkeypatch.setenv("FAKE_DOCKER_IMAGE_ID", FAKE_IMAGE_ID)
    return runtime


def _state(tmp_path) -> dict:
    return json.loads(
        (tmp_path / "fake_docker_state.json").read_text(encoding="utf-8")
    )


# ------------------------------- release mode: no local subprocess, ever


def test_release_shell_without_executor_is_blocked(tmp_path, monkeypatch):
    """Release SandboxIO without an isolated executor must never fall back to
    a local subprocess: the command is blocked and journaled."""
    def no_subprocess(*args, **kwargs):  # pragma: no cover - guard
        raise AssertionError("release shell fell back to local subprocess")

    monkeypatch.setattr(qualify.subprocess, "run", no_subprocess)
    io = qualify.SandboxIO(tmp_path, release_mode=True)
    result = io.shell("git status")
    assert result.startswith("ERROR"), result
    assert io.envelope_violations == 1
    assert io.events[-1].tool == "shell"
    assert io.events[-1].outcome.startswith("rejected")


def test_release_shell_routes_argv_through_executor(tmp_path):
    """The executor interface receives the parsed argv and cwd; outcome,
    exit code and journal entry are derived from the CommandResult."""
    class RecordingExecutor:
        def __init__(self):
            self.calls = []

        def run(self, argv, cwd, timeout):
            self.calls.append({"argv": list(argv), "cwd": Path(cwd), "timeout": timeout})
            return CommandResult("ok", 0, "on branch", "")

    executor = RecordingExecutor()
    io = qualify.SandboxIO(tmp_path, release_mode=True)
    io.command_executor = executor
    result = io.shell("git status")
    assert result.startswith("exit=0"), result
    assert executor.calls[0]["argv"] == ["git", "status"]
    assert executor.calls[0]["cwd"] == tmp_path.resolve()
    event = io.events[-1]
    assert event.exit_code == 0 and event.outcome == "ok"


def test_release_pytest_exit4_is_hallucination_via_executor(tmp_path):
    class Exit4Executor:
        def run(self, argv, cwd, timeout):
            assert argv[0] == "pytest"
            return CommandResult("exit", 4, "", "")

    io = qualify.SandboxIO(tmp_path, release_mode=True)
    io.command_executor = Exit4Executor()
    assert io.shell("pytest -q missing_test.py").startswith("exit=4")
    assert io.hallucinated_paths == 1  # T6 classification survives the executor


def test_release_executor_failure_classified_and_saved(tmp_path):
    class BrokenExecutor:
        def run(self, argv, cwd, timeout):
            raise ExecutorError("command container is not started")

    io = qualify.SandboxIO(tmp_path, release_mode=True)
    io.command_executor = BrokenExecutor()
    result = io.shell("git status")
    assert result.startswith("ERROR"), result
    assert "container_error" in io.events[-1].outcome
    assert io.events[-1].exit_code is None


# ------------------------------------- container command executor contract


def test_command_container_starts_with_sandbox_only_mount(tmp_path, fake_runtime):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    qualify.init_sandbox_git(sandbox)
    executor = ContainerCommandExecutor(fake_runtime, "deltafuse/qual:tag")
    cid = executor.start(sandbox)
    assert cid == "fake-container-id-0001"
    run_argv = _state(tmp_path)["runs"][0]
    # persistent, network-isolated, sandbox-only mount, cwd=/sandbox
    assert "--network" in run_argv and "none" in run_argv
    mount_values = [
        run_argv[i + 1] for i, t in enumerate(run_argv) if t == "-v"
    ]
    assert mount_values == [f"{sandbox.resolve()}:/sandbox"]
    assert not any("qualify.py" in t for t in run_argv)
    assert not any("scripts" in t for t in run_argv)
    assert run_argv[run_argv.index("-w") + 1] == "/sandbox"


def test_command_container_executes_argv_and_returns_output(tmp_path, fake_runtime):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    qualify.init_sandbox_git(sandbox)
    executor = ContainerCommandExecutor(fake_runtime, "deltafuse/qual:tag")
    executor.start(sandbox)
    result = executor.run(["git", "status"], cwd=sandbox, timeout=60)
    assert result.kind == "ok" and result.exit_code == 0
    # raw argv passes through: no shell, no wrapper script, no python preamble
    assert _state(tmp_path)["execs"][-1] == [
        "exec", "fake-container-id-0001", "git", "status",
    ]
    executor.stop()
    assert _state(tmp_path)["stops"], "container must be stopped after the run"


def test_command_container_rejects_foreign_cwd(tmp_path, fake_runtime):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    executor = ContainerCommandExecutor(fake_runtime, "deltafuse/qual:tag")
    executor.start(sandbox)
    with pytest.raises(ExecutorError, match="sandbox"):
        executor.run(["git", "status"], cwd=tmp_path, timeout=10)


def test_command_container_timeout_classified(tmp_path, fake_runtime, monkeypatch):
    monkeypatch.setenv("FAKE_DOCKER_EXEC_MODE", "timeout")
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    executor = ContainerCommandExecutor(fake_runtime, "deltafuse/qual:tag")
    executor.start(sandbox)
    result = executor.run(["git", "status"], cwd=sandbox, timeout=2)
    assert result.kind == "timeout" and result.exit_code is None


def test_command_container_runtime_error_classified(tmp_path, fake_runtime, monkeypatch):
    monkeypatch.setenv("FAKE_DOCKER_EXEC_MODE", "runtime-error")
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    executor = ContainerCommandExecutor(fake_runtime, "deltafuse/qual:tag")
    executor.start(sandbox)
    result = executor.run(["git", "status"], cwd=sandbox, timeout=30)
    assert result.kind == "container_error"
    assert result.stderr.strip()


def test_command_container_exit_and_malformed_output_classified(
    tmp_path, fake_runtime, monkeypatch
):
    monkeypatch.setenv("FAKE_DOCKER_EXEC_MODE", "exit3-malformed")
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    executor = ContainerCommandExecutor(fake_runtime, "deltafuse/qual:tag")
    executor.start(sandbox)
    result = executor.run(["git", "status"], cwd=sandbox, timeout=30)
    assert result.kind == "exit" and result.exit_code == 3
    assert "malformed" in (result.detail or "")


def test_local_command_executor_canonizes_interpreter(tmp_path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    executor = LocalCommandExecutor(
        interpreter=sys.executable, env={**os.environ}
    )
    result = executor.run(["python", "-c", "print('hello')"], cwd=tmp_path, timeout=60)
    assert result.kind == "ok" and "hello" in result.stdout
    result = executor.run(["pytest", "--version"], cwd=tmp_path, timeout=120)
    assert result.kind == "ok", result.stderr


# ------------------------------------- release executor gate: digest only


def test_release_executor_requires_digest_image_reference(monkeypatch):
    """A mutable tag is never accepted for release; the digest reference is."""
    executor = qualify_executor.IsolatedExecutor(image="deltafuse/qual:v1")
    assert not executor.release_ready
    good = qualify_executor.IsolatedExecutor(image=FAKE_IMAGE_ID)
    assert good.release_ready
    # resolve_executor enforces the gate before any Worker call
    monkeypatch.setenv("DELTAFUSE_QUAL_IMAGE", "deltafuse/qual:v1")
    monkeypatch.setattr(qualify_executor.IsolatedExecutor, "available", lambda self: True)
    with pytest.raises(ExecutorUnavailable, match="digest"):
        qualify_executor.resolve_executor("isolated")

    monkeypatch.setenv("DELTAFUSE_QUAL_IMAGE", FAKE_IMAGE_ID)
    assert qualify_executor.resolve_executor("isolated") is not None


def test_attestation_compares_measured_image_digest(monkeypatch):
    manifest = {
        "image_id": FAKE_IMAGE_ID,
        "wheel_sha256": "a" * 64,
        "commit": "a" * 40,
    }
    executor = qualify_executor.IsolatedExecutor(image=FAKE_IMAGE_ID)
    monkeypatch.setattr(
        executor, "inspect_image_id", lambda: FAKE_IMAGE_ID, raising=False
    )
    attestation = executor.attest(image_manifest=manifest)
    assert attestation["image_digest"]["value"] == FAKE_IMAGE_ID
    assert attestation["image_digest"]["provenance"] == "measured"
    assert attestation["wheel_sha256"]["value"] == "a" * 64

    monkeypatch.setattr(
        executor, "inspect_image_id", lambda: "sha256:" + "f" * 64, raising=False
    )
    with pytest.raises(ExecutorError, match="digest"):
        executor.attest(image_manifest=manifest)


# --------------------------------------- judge-side worker loop integration


def test_drive_worker_release_mode_uses_command_executor(tmp_path, monkeypatch, fake_runtime):
    """The Worker loop itself stays judge-side; only shell argv crosses the
    boundary through the command executor."""
    from deltafuse import cli as cli_mod

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    qualify.init_sandbox_git(sandbox)
    monkeypatch.setattr(
        cli_mod, "main",
        lambda argv: print(json.dumps({"envelope": {"write": ["**"]}})) or 0,
    )
    monkeypatch.setattr(
        qualify, "worker_turn",
        lambda base_url, model, messages: {
            "content": '{"tool": "shell", "command": "git status"}', "prompt_tokens": 10,
        },
    )
    executor = ContainerCommandExecutor(fake_runtime, "deltafuse/qual:tag")
    executor.start(sandbox)
    try:
        metrics = qualify.drive_worker(
            sandbox, "http://x", "m", "case", "system",
            command_executor=executor, release_mode=True,
        )
    finally:
        executor.stop()
    shell_events = [e for e in metrics["tool_events"] if e["tool"] == "shell"]
    assert shell_events and shell_events[0]["outcome"] == "ok"
    assert shell_events[0]["exit_code"] == 0


# --------------------------------------------- canonical image build script


def _fake_wheel(tmp_path: Path) -> Path:
    wheel = tmp_path / "deltafuse-3.0.0-py3-none-any.whl"
    wheel.write_bytes(b"PK\x03\x04 fake wheel for tests")
    return wheel


def test_build_qual_image_records_measured_digest_and_wheel_sha(tmp_path, monkeypatch):
    import build_qual_image

    wheel = _fake_wheel(tmp_path)

    def fake_build_wheel(repo, dist, record):
        record(subprocess.CompletedProcess(["pip", "wheel"], 0))
        return wheel

    monkeypatch.setattr(build_qual_image, "_build_wheel", fake_build_wheel, raising=False)
    monkeypatch.setattr(build_qual_image, "tree_dirty", lambda repo: [])
    monkeypatch.setattr(
        build_qual_image, "framework_commit", lambda repo: "a" * 40, raising=False
    )
    monkeypatch.setattr(
        build_qual_image, "package_version", lambda repo: "3.0.0", raising=False
    )
    fake_runtime = _write_fake_runtime(tmp_path)
    monkeypatch.setenv("FAKE_DOCKER_STATE", str(tmp_path / "fake_docker_state.json"))
    monkeypatch.setenv("FAKE_DOCKER_IMAGE_ID", FAKE_IMAGE_ID)
    (tmp_path / "fake_docker_state.json").write_text("{}", encoding="utf-8")
    out_dir = tmp_path / "builds"
    rc = build_qual_image.main([
        "--output-dir", str(out_dir),
        "--runtime", fake_runtime,
        "--repo", str(tmp_path / "repo-not-needed"),
    ])
    assert rc == 0
    manifests = list(out_dir.glob("qual-image-*.json"))
    assert len(manifests) == 1
    data = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert data["image_id"] == FAKE_IMAGE_ID
    assert data["wheel_sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert data["commit"] == "a" * 40
    assert data["tree_clean"] is True
    build_qual_image.validate_manifest(data)  # must not raise

    # an image whose measured digest differs from the manifest never attests
    monkeypatch.setenv("FAKE_DOCKER_IMAGE_ID", "sha256:" + "d" * 64)
    executor = qualify_executor.IsolatedExecutor(image=FAKE_IMAGE_ID)
    monkeypatch.setattr(executor, "inspect_image_id",
                        lambda: "sha256:" + "d" * 64, raising=False)
    with pytest.raises(ExecutorError, match="digest"):
        executor.attest(image_manifest=data)


def test_containerfile_has_no_judge_surface():
    """The canonical Containerfile copies only the wheel; no script, pack or
    checkout path may enter the image."""
    repo = Path(__file__).resolve().parents[2]
    text = (repo / "scripts" / "Containerfile.qual").read_text(encoding="utf-8")
    assert "deltafuse-*.whl" in text
    assert "pytest" in text and "git" in text
    for forbidden in ("qualify.py", "process/", "COPY . ", "ADD . "):
        assert forbidden not in text, forbidden
