"""QF-019 live check: the command container executes allowed argv in the
wheel-only image. Requires a responding docker/podman daemon plus
DELTAFUSE_QUAL_IMAGE (digest reference); otherwise SKIP — a skip is never
release evidence (QF-025 requires a saved live run).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, "scripts")

import qualify_executor  # noqa: E402

_executor = None
try:
    candidate = qualify_executor.IsolatedExecutor()
    if candidate.available():
        _executor = candidate
except Exception:
    _executor = None

pytestmark = pytest.mark.skipif(
    _executor is None,
    reason="no command container available (docker/podman daemon + DELTAFUSE_QUAL_IMAGE)",
)


def _session(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    session = _executor.command_session(sandbox)
    return session, sandbox


def test_live_allowed_commands_run_in_command_container(tmp_path):
    session, sandbox = _session(tmp_path)
    try:
        for argv in (["git", "--version"], ["pytest", "--version"],
                     ["deltafuse", "--help"]):
            result = session.run(argv, cwd=sandbox, timeout=120)
            assert result.kind == "ok", (argv, result.stderr)
    finally:
        session.stop()


def test_live_judge_material_absent_from_container(tmp_path):
    session, sandbox = _session(tmp_path)
    try:
        probe = session.run(
            ["python", "-c",
             "import os; print(os.path.exists('/opt/qualify.py'), "
             "os.path.exists('/sandbox') )"],
            cwd=sandbox, timeout=60,
        )
        assert probe.kind == "ok", probe.stderr
        assert probe.stdout.strip().endswith("True")  # sandbox present...
        exists_qualify = session.run(
            ["python", "-c", "import os; print(os.path.exists('/opt/qualify.py'))"],
            cwd=sandbox, timeout=60,
        )
        assert exists_qualify.stdout.strip() == "False"  # ...judge script absent
    finally:
        session.stop()
