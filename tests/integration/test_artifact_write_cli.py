"""`deltafuse artifact write` through the real CLI process: what the retired create/update tests held.

The legacy `artifact describe|create|update|validate|update-index` subcommands were removed
(codebase audit 2026-10-21, owner decision): no skill and no bench run used them. Their CLI tests
also pinned properties of the Writer's command boundary; these hold for `write`, the one path left.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.unit.test_artifact_write import TASK, _specified

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(change_dir: Path, payload: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "deltafuse.cli", "artifact", "write", "--kind", "task",
         "--change", str(change_dir), "--input", "-", "--json"],
        input=payload, capture_output=True, text=True, encoding="utf-8", env=env,
    )


def test_a_task_written_through_stdin_is_created_with_a_receipt(tmp_path: Path, repo_root: Path):
    builder = _specified(tmp_path, repo_root, "CHG-701")
    proc = _write(builder.change_dir, json.dumps({"identity": "TASK-011", "fields": TASK, "body": "Prose.\n"}))
    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(proc.stdout)
    assert receipt["ok"] is True and receipt["operation"] == "create"
    assert (builder.change_dir / "tasks" / "TASK-011.md").is_file()


def test_a_core_owned_field_is_a_policy_refusal_and_writes_nothing(tmp_path: Path, repo_root: Path):
    builder = _specified(tmp_path, repo_root, "CHG-702")
    proc = _write(builder.change_dir, json.dumps({"identity": "TASK-012", "fields": {**TASK, "status": "verified"}}))
    assert proc.returncode == 3, proc.stderr
    assert json.loads(proc.stdout)["error"]["code"] == "core_owned_field"
    assert not (builder.change_dir / "tasks" / "TASK-012.md").exists()


def test_a_duplicate_json_key_is_refused_before_anything_is_written(tmp_path: Path, repo_root: Path):
    builder = _specified(tmp_path, repo_root, "CHG-703")
    body = json.dumps({"fields": TASK})[1:]
    proc = _write(builder.change_dir, '{"identity": "TASK-013", "identity": "TASK-014", ' + body)
    assert proc.returncode == 2, proc.stderr
    assert "not valid JSON" in proc.stderr
    assert not any((builder.change_dir / "tasks").glob("TASK-01[34]*.md"))
