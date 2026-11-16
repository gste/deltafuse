"""`--timeout` stops the whole test run, not only the program the Worker named.

Audit 2026-11-16 (df-evidence #9): Maven on Windows is `mvn.cmd`, which cmd.exe runs, and cmd.exe
starts java. `subprocess.run(timeout=...)` killed cmd.exe only; java kept the output pipes open, so
a 10 s timeout took 49.6 s and a test that hangs hung `deltafuse evidence` with it. The runner here
is a batch file (a shell script elsewhere) whose child sleeps far past the timeout.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from deltafuse.core.evidence import run_evidence
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder


def _runner(root: Path) -> list[str]:
    sleeper = f'"{sys.executable}" -c "import time; time.sleep(120)"'
    if os.name == "nt":
        (root / "slow.cmd").write_text(f"@echo off\r\n{sleeper}\r\n", encoding="utf-8")
        return ["./slow.cmd"]
    script = root / "slow.sh"
    script.write_text(f"#!/bin/sh\n{sleeper}\n", encoding="utf-8")
    script.chmod(0o755)
    return ["./slow.sh"]


def test_timeout_kills_the_runners_children_too(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-210", title="Timeout").step_through_decompose()
    argv = _runner(tmp_path)
    started = time.monotonic()
    outcome = run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=argv, timeout=3)
    elapsed = time.monotonic() - started
    assert outcome.payload["result"] == "blocked"
    assert outcome.payload["exit_code"] == 124
    assert any("timed out after 3s" in e for e in outcome.errors)
    assert elapsed < 30, f"evidence waited {elapsed:.1f}s for a 3s timeout"
