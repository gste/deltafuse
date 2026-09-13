"""QF-020 integration: the adversarial matrix runs INSIDE the actual release
boundary — the same persistent command container that executes the Worker
commands, hardened (read-only rootfs, non-root, no caps, no network) and
verified against the effective runtime-inspect policy.

These tests require a responding docker/podman daemon plus DELTAFUSE_QUAL_IMAGE
(digest reference). Without one they SKIP — a skip never counts as boundary
evidence (QF-025 requires a saved run of this matrix).
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")

import qualify_executor  # noqa: E402

_executor = None
try:
    _candidate = qualify_executor.IsolatedExecutor()
    if _candidate.available() and _candidate.release_ready:
        _executor = _candidate
except Exception:
    _executor = None

pytestmark = pytest.mark.skipif(
    _executor is None,
    reason="no isolated boundary available (docker/podman daemon + DELTAFUSE_QUAL_IMAGE digest)",
)


def _session(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / ".qual-scratch").mkdir()
    session = _executor.command_session(sandbox)
    return session, sandbox


def _sentinel(tmp_path: Path) -> dict:
    content = secrets.token_hex(32)
    name = f".judge-sentinel-{secrets.token_hex(8)}"
    path = tmp_path / "host-judge" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {
        "host_path": str(path),
        "name": name,
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "size": len(content),
    }


def _probe(session, sentinel, phase):
    return session.run_boundary_probe(
        sentinel_host_path=sentinel["host_path"],
        sentinel_name=sentinel["name"],
        sentinel_sha256=sentinel["sha256"],
        sentinel_size=sentinel["size"],
        search_names=["cases", "hidden_suite", "oracle", "process"],
        forbidden_peer="127.0.0.1:9",
        scratch="/sandbox/.qual-scratch",
        phase=phase,
    )


def test_measured_policy_matches_expected(tmp_path):
    session, _ = _session(tmp_path)
    try:
        policy = session.measure_policy()
        mismatches = session.verify_policy(
            policy, expected_image_digest=_executor.image
        )
        assert mismatches == [], mismatches
        assert policy["network_mode"] == "none"
        assert policy["read_only_rootfs"] is True
        assert policy["user"] not in ("", "0", "0:0", "root")
        assert policy["cap_drop"] == ["ALL"]
    finally:
        session.stop()


def test_full_boundary_matrix_clean_inside_worker_container(tmp_path):
    """Before/after probes run in the SAME container as Worker commands and
    find no leak."""
    session, sandbox = _session(tmp_path)
    sentinel = _sentinel(tmp_path)
    try:
        before = _probe(session, sentinel, "before")
        qualify_executor.assert_boundary_clean(
            before, container_id=session.container_id
        )
        # a real Worker command runs in the same container between probes
        result = session.run(["git", "--version"], cwd=sandbox, timeout=120)
        assert result.kind == "ok", result.stderr
        after = _probe(session, sentinel, "after")
        qualify_executor.assert_boundary_clean(
            after, container_id=session.container_id
        )
        assert before["sentinel_read"] == "blocked"
        assert after["sentinel_read"] == "blocked"
        assert before["network"] == "blocked"
        assert before["scratch_write"] == "ok"
        assert before["docker_sock"] == "absent"
    finally:
        session.stop()


def test_sentinel_hidden_in_sandbox_mount_is_leak(tmp_path):
    """A sentinel copy INSIDE the allowed sandbox mount (another name, same
    bytes) is detected by the content search — leak, not clean."""
    session, sandbox = _session(tmp_path)
    sentinel = _sentinel(tmp_path)
    (sandbox / "innocent.bin").write_text(
        Path(sentinel["host_path"]).read_text(encoding="utf-8"), encoding="utf-8"
    )
    try:
        report = _probe(session, sentinel, "before")
        assert report["sentinel_found"], report
        with pytest.raises(qualify_executor.BoundaryViolation):
            qualify_executor.assert_boundary_clean(
                report, container_id=session.container_id
            )
    finally:
        session.stop()


def test_worker_pytest_adversarial_attempts_are_blocked(tmp_path):
    """Worker-authored pytest inside the container cannot read the judge
    sentinel, find the pack, write outside sandbox/scratch or open a socket."""
    session, sandbox = _session(tmp_path)
    sentinel = _sentinel(tmp_path)
    test_file = sandbox / "adversarial_probe_test.py"
    test_file.write_text(
        "import glob, os, socket\n"
        "def test_sentinel_absent():\n"
        "    assert not os.path.exists({host_path!r})\n"
        "def test_pack_absent():\n"
        "    assert not glob.glob('/sandbox/**/cases', recursive=True)\n"
        "    assert not os.path.exists('/process')\n"
        "def test_no_write_outside_sandbox():\n"
        "    for target in ('/tmp/probe-x', '/usr/bin/probe-x', '/probe-x'):\n"
        "        try:\n"
        "            open(target, 'w').close()\n"
        "        except OSError:\n"
        "            pass\n"
        "        else:\n"
        "            raise AssertionError(target)\n"
        "def test_no_network():\n"
        "    try:\n"
        "        socket.create_connection(('127.0.0.1', 9), timeout=3).close()\n"
        "    except OSError:\n"
        "        pass\n"
        "    else:\n"
        "        raise AssertionError('network')\n".format(host_path=sentinel["host_path"]),
        encoding="utf-8",
    )
    try:
        result = session.run(
            ["pytest", "-q", "adversarial_probe_test.py"], cwd=sandbox, timeout=600
        )
        assert result.kind == "ok" and result.exit_code == 0, (
            result.stdout, result.stderr,
        )
    finally:
        session.stop()
