"""Integration tests for Artifact Writer CLI subprocess invocations (AW-11).

Executes `python -m deltafuse.cli artifact ...` in external subprocesses without
shell interpolation to verify exit codes, stdin piping, and file outputs.
"""

import json
from pathlib import Path
import subprocess
import sys
import pytest


def test_subprocess_artifact_describe():
    cmd = [sys.executable, "-m", "deltafuse.cli", "artifact", "describe", "--kind", "task", "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["kind"] == "task"
    assert "creatable_semantic_fields" in data or "allowed_semantic_fields" in data


def test_subprocess_artifact_create_via_stdin(tmp_path):
    (tmp_path / "slices").mkdir(parents=True, exist_ok=True)
    (tmp_path / "slices" / "SLICE-01.md").write_text("---\nid: SLICE-01\nchange: CHG-001\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n", encoding="utf-8")
    (tmp_path / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "overview.md").write_text("# Spec\n", encoding="utf-8")

    cmd = [
        sys.executable, "-m", "deltafuse.cli",
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", "-",
        "--json",
    ]
    payload = {
        "identity": "TASK-100",
        "semantic_payload": {
            "title": "Subprocess Created Task",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": "# TASK-100: Subprocess Created Task\n\nSubprocess test body.",
    }
    input_text = json.dumps(payload, ensure_ascii=False)
    proc = subprocess.run(cmd, input=input_text, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    receipt = json.loads(proc.stdout)
    assert receipt["outcome"] == "committed"

    task_file = tmp_path / "tasks" / "TASK-100.md"
    assert task_file.is_file()
    assert "Subprocess Created Task" in task_file.read_text(encoding="utf-8")


def test_subprocess_artifact_core_owned_field_denied(tmp_path):
    cmd = [
        sys.executable, "-m", "deltafuse.cli",
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", "-",
        "--json",
    ]
    payload = {
        "identity": "TASK-101",
        "semantic_payload": {
            "title": "Denied Task",
            "status": "verified",
        },
    }
    input_text = json.dumps(payload)
    proc = subprocess.run(cmd, input=input_text, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 3
    assert not (tmp_path / "tasks" / "TASK-101.md").exists()
