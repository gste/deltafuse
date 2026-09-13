"""QF-020: the boundary probe runs in the SAME persistent command container
as the Worker commands, under one measured policy (image digest, mounts,
user, capabilities, rootfs, network) — a declared tag is never enough.

Red evidence pins:
- hardened container start flags (read-only rootfs, non-root, drop caps,
  no-new-privileges, memory/pids limits, scratch HOME/TMPDIR in sandbox);
- effective policy measured from runtime inspect and verified;
- in-container probe before/after the Worker phase: judge sentinel (host
  path AND unique name AND exact content hash), pack markers, writes outside
  sandbox/scratch, rootfs and runtime control paths, network, identity;
- a sentinel hidden inside the mounted sandbox is a LEAK (this replaces the
  old probe that only probed a host path and could not see mount copies);
- scratch directories are accounted infrastructure, never unjournaled changes.

Live-container execution of the adversarial matrix lives in
tests/integration/test_qualify_isolated_boundary.py (skip without daemon).
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")

import qualify  # noqa: E402
import qualify_executor  # noqa: E402
from qualify_executor import (  # noqa: E402
    BoundaryViolation,
    ContainerCommandExecutor,
)

FAKE_IMAGE_ID = "sha256:" + "e" * 64


# ----------------------------------------------------------------- helpers


def _write_fake_runtime(tmp_path: Path, mode_override: str | None = None) -> str:
    """A scripted fake container runtime recording run/exec argv and
    replaying canned behaviors (see tests for QF-019)."""
    handler = tmp_path / "fake_docker_handler.py"
    handler.write_text(_FAKE_DOCKER_HANDLER, encoding="utf-8")
    state = tmp_path / "fake_docker_state.json"
    state.write_text("{}", encoding="utf-8")
    if os.name == "nt":
        exe = tmp_path / "fake-docker.cmd"
        exe.write_text(f'@echo off\r\n"{sys.executable}" "{handler}" %*\r\n',
                       encoding="utf-8")
    else:
        exe = tmp_path / "fake-docker"
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{handler}" "$@"\n',
                       encoding="utf-8")
        exe.chmod(0o755)
    return str(exe)


_FAKE_DOCKER_HANDLER = r"""
import json, os, sys

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
    if os.environ.get("FAKE_DOCKER_EXEC_MODE") == "leak-report":
        print(json.dumps({"sentinel_read": "LEAK"}))
    else:
        print(json.dumps({"sentinel_read": "blocked", "sentinel_found": [],
                          "pack_found": [], "write_leak": [],
                          "rootfs_write_leak": [], "docker_sock": "absent",
                          "network": "blocked", "scratch_write": "ok",
                          "container_token": None}))
elif args[0] == "stop":
    state.setdefault("stops", []).append(args)
    save(state)
elif args[:2] == ["image", "inspect"]:
    print(os.environ.get("FAKE_DOCKER_IMAGE_ID", "sha256:" + "e" * 64))
"""


@pytest.fixture()
def fake_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_DOCKER_STATE",
                       str(tmp_path / "fake_docker_state.json"))
    monkeypatch.setenv("FAKE_DOCKER_IMAGE_ID", FAKE_IMAGE_ID)
    return _write_fake_runtime(tmp_path)


def _state(tmp_path) -> dict:
    return json.loads(
        (tmp_path / "fake_docker_state.json").read_text(encoding="utf-8")
    )


def _inspect_doc(**overrides) -> dict:
    """A container inspect document satisfying COMMAND_CONTAINER_POLICY."""
    doc = {
        "Id": "cid-1234",
        "Image": FAKE_IMAGE_ID,
        "Config": {"User": "1000:1000"},
        "HostConfig": {
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "Memory": 2147483648,
            "PidsLimit": 256,
        },
        "Mounts": [
            {"Type": "bind", "Destination": "/sandbox", "RW": True,
             "Source": "C:/tmp/sandbox"},
        ],
    }
    for dotted, value in overrides.items():
        section, _, key = dotted.rpartition(".")
        target = doc.get(section) if section else doc
        if target is None:
            target = doc.setdefault(section, {})
        target[key] = value
    return doc


def _patch_inspect(monkeypatch, doc: dict) -> None:
    monkeypatch.setattr(
        qualify_executor.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a[0], 0, stdout=json.dumps([doc]), stderr=""),
    )


def _sentinel(tmp_path: Path) -> dict:
    content = secrets.token_hex(32).encode("utf-8")
    return {
        "content": content,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
        "name": f".judge-sentinel-{secrets.token_hex(8)}",
    }


def _run_probe_script(targets: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", qualify_executor.BOUNDARY_PROBE_SCRIPT],
        input=json.dumps(targets), capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


# --------------------------------------------------------- hardened start


def test_command_container_start_is_hardened(tmp_path, fake_runtime):
    """The command container starts read-only, non-root, without
    capabilities, without new privileges, with resource limits and with
    scratch HOME/TMPDIR inside the sandbox."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    executor = ContainerCommandExecutor(fake_runtime, FAKE_IMAGE_ID)
    executor.start(sandbox)
    argv = _state(tmp_path)["runs"][0]
    for flag in ("--read-only", "--cap-drop", "--security-opt", "--memory",
                 "--pids-limit", "--user"):
        assert flag in argv, flag
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--security-opt") + 1] == "no-new-privileges"
    assert argv[argv.index("--user") + 1] not in ("", "0", "0:0", "root")
    env_values = [argv[i + 1] for i, t in enumerate(argv) if t == "-e"]
    scratch_env = [v for v in env_values if v.startswith(("TMPDIR=", "HOME="))]
    assert {v.split("=", 1)[0] for v in scratch_env} == {"TMPDIR", "HOME"}
    for value in scratch_env:
        assert value.split("=", 1)[1].startswith("/sandbox/"), value


def test_probe_execs_use_the_worker_container_id(tmp_path, fake_runtime):
    """Before/after probes exec into the SAME container as Worker commands —
    one environment, one identity."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    session = ContainerCommandExecutor(fake_runtime, FAKE_IMAGE_ID)
    session.start(sandbox)
    sentinel = _sentinel(tmp_path)
    session.run_boundary_probe(
        sentinel_host_path=str(tmp_path / "host" / sentinel["name"]),
        sentinel_name=sentinel["name"],
        sentinel_sha256=sentinel["sha256"],
        sentinel_size=sentinel["size"],
        search_names=["cases"],
        forbidden_peer="127.0.0.1:9",
        scratch="/sandbox/.qual-scratch",
        phase="before",
    )
    session.run(["git", "status"], cwd=sandbox, timeout=60)
    session.run_boundary_probe(
        sentinel_host_path=str(tmp_path / "host" / sentinel["name"]),
        sentinel_name=sentinel["name"],
        sentinel_sha256=sentinel["sha256"],
        sentinel_size=sentinel["size"],
        search_names=["cases"],
        forbidden_peer="127.0.0.1:9",
        scratch="/sandbox/.qual-scratch",
        phase="after",
    )
    execs = _state(tmp_path)["execs"]
    assert len(execs) == 3
    assert {e[1] for e in execs} == {"fake-container-id-0001"}


# ---------------------------------------------- measured effective policy


def test_policy_measured_from_runtime_inspect(tmp_path, monkeypatch):
    """Effective mounts/digest/user/security/network come from runtime
    inspect, never from the declared invocation."""
    executor = ContainerCommandExecutor("docker", FAKE_IMAGE_ID)
    executor.sandbox = tmp_path
    executor.container_id = "cid-1234"
    _patch_inspect(monkeypatch, _inspect_doc())
    policy = executor.measure_policy()
    assert policy["container_id"] == "cid-1234"
    assert policy["network_mode"] == "none"
    assert policy["read_only_rootfs"] is True
    assert policy["user"] == "1000:1000"
    assert policy["cap_drop"] == ["ALL"]
    assert policy["image_digest"] == FAKE_IMAGE_ID
    assert executor.verify_policy(policy) == []


@pytest.mark.parametrize("override,fragment", [
    ({"HostConfig.NetworkMode": "bridge"}, "network"),
    ({"HostConfig.NetworkMode": "default"}, "network"),
    ({"HostConfig.ReadonlyRootfs": False}, "rootfs"),
    ({"Config.User": "root"}, "user"),
    ({"Config.User": ""}, "user"),
    ({"HostConfig.CapDrop": []}, "cap"),
    ({"HostConfig.SecurityOpt": []}, "privileges"),
    ({"HostConfig.Memory": 0}, "memory"),
    ({"HostConfig.PidsLimit": 0}, "pids"),
])
def test_policy_mismatch_detected(override, fragment, tmp_path, monkeypatch):
    executor = ContainerCommandExecutor("docker", FAKE_IMAGE_ID)
    executor.sandbox = tmp_path
    executor.container_id = "cid-1234"
    _patch_inspect(monkeypatch, _inspect_doc(**override))
    mismatches = executor.verify_policy(executor.measure_policy())
    assert any(fragment in m for m in mismatches), mismatches
    with pytest.raises(BoundaryViolation):
        qualify_executor.assert_policy_clean(mismatches)


def test_extra_mount_is_policy_mismatch(tmp_path, monkeypatch):
    """Any mount beyond the run sandbox fails the measured policy."""
    executor = ContainerCommandExecutor("docker", FAKE_IMAGE_ID)
    executor.sandbox = tmp_path
    executor.container_id = "cid-1234"
    doc = _inspect_doc()
    doc["Mounts"].append({"Type": "bind", "Destination": "/judge",
                          "RW": False, "Source": "C:/repo"})
    _patch_inspect(monkeypatch, doc)
    mismatches = executor.verify_policy(executor.measure_policy())
    assert any("mount" in m for m in mismatches), mismatches


def test_image_digest_drift_between_probe_and_run(tmp_path, monkeypatch):
    """The container image digest is measured; drift from the manifest
    digest is a violation, not a declared identity."""
    executor = ContainerCommandExecutor("docker", FAKE_IMAGE_ID)
    executor.sandbox = tmp_path
    executor.container_id = "cid-1234"
    _patch_inspect(monkeypatch, _inspect_doc(Image="sha256:" + "a" * 64))
    policy = executor.measure_policy()
    with pytest.raises(BoundaryViolation):
        qualify_executor.assert_policy_clean(
            executor.verify_policy(policy, expected_image_digest=FAKE_IMAGE_ID)
        )


# ------------------------------------------------ in-container probe matrix


def test_probe_clean_targets_are_clean(tmp_path):
    """Negative controls: no sentinel, no pack, no writes, no network."""
    sentinel = _sentinel(tmp_path)
    sandbox = tmp_path / "sandbox"
    (sandbox / ".qual-scratch").mkdir(parents=True)
    report = _run_probe_script({
        "sentinel_host_path": str(tmp_path / "not" / "visible" / sentinel["name"]),
        "sentinel_name": sentinel["name"],
        "sentinel_sha256": sentinel["sha256"],
        "sentinel_size": sentinel["size"],
        "search_names": ["cases", "hidden_suite", "oracle"],
        "search_roots": [str(sandbox)],
        "write_roots": [str(tmp_path / "does-not-exist")],
        "rootfs_write_probes": [str(tmp_path / "also-missing")],
        "forbidden_peer": "127.0.0.1:9",
        "scratch": str(sandbox / ".qual-scratch"),
    })
    qualify_executor.assert_boundary_clean(report, container_id=None)  # no raise


def test_probe_detects_sentinel_hidden_inside_mount(tmp_path):
    """The old false negative: a sentinel inside the (allowed) sandbox mount
    under another path must be found by name — leak, never clean."""
    sentinel = _sentinel(tmp_path)
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / sentinel["name"]).write_bytes(sentinel["content"])
    report = _run_probe_script({
        "sentinel_host_path": str(tmp_path / "host" / sentinel["name"]),
        "sentinel_name": sentinel["name"],
        "sentinel_sha256": sentinel["sha256"],
        "sentinel_size": sentinel["size"],
        "search_names": [],
        "search_roots": [str(sandbox)],
        "write_roots": [],
        "forbidden_peer": "127.0.0.1:9",
        "scratch": str(sandbox / ".qual-scratch"),
    })
    assert report["sentinel_found"], "probe must find the sentinel by name"
    with pytest.raises(BoundaryViolation, match="sentinel"):
        qualify_executor.assert_boundary_clean(report)


def test_probe_detects_host_path_hidden_in_mount_by_content(tmp_path):
    """The host path does not exist inside the container, but the same bytes
    are reachable through the mount under a different name: leak, not
    `blocked`."""
    sentinel = _sentinel(tmp_path)
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "innocent.bin").write_bytes(sentinel["content"])
    report = _run_probe_script({
        "sentinel_host_path": str(tmp_path / "host" / "sentinel"),
        "sentinel_name": sentinel["name"],
        "sentinel_sha256": sentinel["sha256"],
        "sentinel_size": sentinel["size"],
        "search_names": [],
        "search_roots": [str(sandbox)],
        "write_roots": [],
        "forbidden_peer": "127.0.0.1:9",
        "scratch": str(sandbox / ".qual-scratch"),
    })
    assert report["sentinel_read"] == "blocked"  # host path itself invisible
    assert report["sentinel_found"], "content hash search must find the copy"
    with pytest.raises(BoundaryViolation):
        qualify_executor.assert_boundary_clean(report)


def test_probe_detects_writable_rootfs(tmp_path):
    """A writable 'rootfs' target is a leak."""
    sentinel = _sentinel(tmp_path)
    writable = tmp_path / "writable-rootfs"
    writable.mkdir()
    report = _run_probe_script({
        "sentinel_host_path": str(tmp_path / "missing"),
        "sentinel_name": sentinel["name"],
        "sentinel_sha256": sentinel["sha256"],
        "sentinel_size": sentinel["size"],
        "search_names": [],
        "search_roots": [],
        "write_roots": [],
        "rootfs_write_probes": [str(writable)],
        "forbidden_peer": "127.0.0.1:9",
        "scratch": str(tmp_path / "scratch-ok"),
    })
    assert report["rootfs_write_leak"] == [str(writable)]
    with pytest.raises(BoundaryViolation, match="rootfs"):
        qualify_executor.assert_boundary_clean(report)


def test_probe_reports_control_socket_state(tmp_path):
    """The runtime control socket is probed; presence/writability is a leak."""
    sentinel = _sentinel(tmp_path)
    sock = tmp_path / "docker.sock"
    sock.write_text("", encoding="utf-8")
    report = _run_probe_script({
        "sentinel_host_path": str(tmp_path / "missing"),
        "sentinel_name": sentinel["name"],
        "sentinel_sha256": sentinel["sha256"],
        "sentinel_size": sentinel["size"],
        "search_names": [],
        "search_roots": [],
        "write_roots": [],
        "rootfs_write_probes": [],
        "control_socket": str(sock),
        "forbidden_peer": "127.0.0.1:9",
        "scratch": str(tmp_path / "scratch-ok"),
    })
    assert report["docker_sock"] in ("present", "writable")
    with pytest.raises(BoundaryViolation, match="socket"):
        qualify_executor.assert_boundary_clean(report)


def test_probe_flags_blocked_scratch_as_leak(tmp_path):
    """A scratch the Worker cannot write to breaks the run contract: the
    boundary is reported, not silently tolerated."""
    sentinel = _sentinel(tmp_path)
    scratch_parent = tmp_path / "ro-scratch-parent"
    scratch_parent.write_text("file, not a dir", encoding="utf-8")
    report = _run_probe_script({
        "sentinel_host_path": str(tmp_path / "missing"),
        "sentinel_name": sentinel["name"],
        "sentinel_sha256": sentinel["sha256"],
        "sentinel_size": sentinel["size"],
        "search_names": [],
        "search_roots": [],
        "write_roots": [],
        "rootfs_write_probes": [],
        "forbidden_peer": "127.0.0.1:9",
        "scratch": str(scratch_parent / "scratch"),
    })
    assert report["scratch_write"] == "blocked"
    with pytest.raises(BoundaryViolation, match="scratch"):
        qualify_executor.assert_boundary_clean(report)


def test_probe_container_identity_mismatch_is_leak():
    """Identity measured inside the container must match the session
    container id."""
    report = {"container_token": "b" * 64}
    with pytest.raises(BoundaryViolation, match="identity"):
        qualify_executor.assert_boundary_clean(report, container_id="c" * 64)
    # unknown token (runtime without a parseable cgroup id) is tolerated
    qualify_executor.assert_boundary_clean({"container_token": None},
                                           container_id="c" * 64)


# ------------------------------------------------- run-level fail-closed flow


def test_boundary_violation_blocks_the_run(tmp_path, monkeypatch, tmp_path_factory):
    """A leaking boundary blocks the run fail-closed with a dedicated error
    class instead of producing Worker metrics."""
    leak_dir = tmp_path_factory.mktemp("leak")
    monkeypatch.setenv("FAKE_DOCKER_STATE", str(leak_dir / "state.json"))
    monkeypatch.setenv("FAKE_DOCKER_IMAGE_ID", FAKE_IMAGE_ID)
    runtime = leak_dir / "fake-docker-leak.py"
    runtime.write_text(
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "state_path = os.environ['FAKE_DOCKER_STATE']\n"
        "state = json.load(open(state_path, encoding='utf-8')) if "
        "os.path.exists(state_path) else {}\n"
        "if args[0] == 'run':\n"
        "    state.setdefault('runs', []).append(args)\n"
        "    json.dump(state, open(state_path, 'w', encoding='utf-8'))\n"
        "    print('fake-container-id-0001')\n"
        "elif args[0] == 'exec':\n"
        "    print(json.dumps({'sentinel_read': 'LEAK'}))\n"
        "elif args[0] == 'inspect':\n"
        "    print(json.dumps([{'Id': 'fake-container-id-0001',\n"
        "        'Image': 'sha256:' + 'e' * 64, 'Config': {'User': '1000:1000'},\n"
        "        'HostConfig': {'NetworkMode': 'none', 'ReadonlyRootfs': True,\n"
        "                      'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'],\n"
        "                      'Memory': 2147483648, 'PidsLimit': 256},\n"
        "        'Mounts': [{'Type': 'bind', 'Destination': '/sandbox',\n"
        "                    'RW': True, 'Source': 'x'}]}]))\n"
        "elif args[:2] == ['image', 'inspect']:\n"
        "    print('sha256:' + 'e' * 64)\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        exe = leak_dir / "fake-docker-leak.cmd"
        exe.write_text(f'@echo off\r\n"{sys.executable}" "{runtime}" %*\r\n',
                       encoding="utf-8")
    else:
        exe = leak_dir / "fake-docker-leak"
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{runtime}" "$@"\n',
                       encoding="utf-8")
        exe.chmod(0o755)

    from deltafuse.bench import init_product as init_mod
    from deltafuse.bench import score as score_mod

    monkeypatch.setattr(
        init_mod, "init_bench_product",
        lambda case, sandbox, framework_root=None: sandbox.mkdir(
            parents=True, exist_ok=True),
    )
    monkeypatch.setattr(qualify, "_system_prompt", lambda sandbox: "system")
    monkeypatch.setattr(
        score_mod, "score_product",
        lambda sandbox, pack_root=None: {"stages": {}, "retries": {}},
    )
    monkeypatch.setattr(qualify, "RUNS_DIR", tmp_path / "bench" / "runs")

    executor = qualify_executor.IsolatedExecutor(image=FAKE_IMAGE_ID)
    executor.runtime = str(exe)
    with pytest.raises(qualify.BoundaryBlocked):
        qualify.run_case(
            "M01-cooldown", 1, "camp",
            {"host_base_url": {"value": "http://x"}, "id": {"value": "m"}},
            {"commit": "a" * 40}, executor_kind="isolated", executor=executor,
        )
    assert not executor.probe_reports


def test_scratch_dirs_are_never_unjournaled_changes(tmp_path):
    """Scratch/HOME directories inside the sandbox are accounted
    infrastructure: their contents never appear as unjournaled changes."""
    sandbox = tmp_path / "sandbox"
    (sandbox / ".qual-scratch").mkdir(parents=True)
    (sandbox / ".qual-home").mkdir(parents=True)
    (sandbox / ".qual-scratch" / "pytest-tmp.bin").write_text("x", encoding="utf-8")
    (sandbox / ".qual-home" / "gitconfig").write_text("x", encoding="utf-8")
    qualify.init_sandbox_git(sandbox)
    inv = qualify.inventory(sandbox)
    assert not any(p.startswith(".qual-") for p in inv), inv
