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
    (tmp_path / ".deltafuse").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        "  version: 3.1.0\n"
        "  source: deltafuse\n"
        "  content_hash: sha256:17786cb040d1ed3cd5636dd4a6b97453c1b77627\n"
        "workflow:\n"
        "  call_width: wide\n"
        "  auto_accept_decisions: false\n",
        encoding="utf-8",
    )
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
    (tmp_path / ".deltafuse").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        "  version: 3.1.0\n"
        "  source: deltafuse\n"
        "  content_hash: sha256:17786cb040d1ed3cd5636dd4a6b97453c1b77627\n"
        "workflow:\n"
        "  call_width: wide\n"
        "  auto_accept_decisions: false\n",
        encoding="utf-8",
    )
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



def test_subprocess_artifact_update_retry_and_idempotency(tmp_path):
    import hashlib

    (tmp_path / ".deltafuse").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        "  version: 3.1.0\n"
        "  source: deltafuse\n"
        "  content_hash: sha256:17786cb040d1ed3cd5636dd4a6b97453c1b77627\n"
        "workflow:\n"
        "  call_width: wide\n"
        "  auto_accept_decisions: false\n",
        encoding="utf-8",
    )
    (tmp_path / "slices").mkdir(parents=True, exist_ok=True)
    (tmp_path / "slices" / "SLICE-01.md").write_text("---\nid: SLICE-01\nchange: CHG-001\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n", encoding="utf-8")
    (tmp_path / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "overview.md").write_text("# Spec\n", encoding="utf-8")

    cmd_create = [
        sys.executable, "-m", "deltafuse.cli",
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", "-",
        "--json",
    ]
    create_payload = {
        "request_id": "cli-req-cr-1",
        "identity": "TASK-200",
        "semantic_payload": {
            "title": "CLI Task",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": "# TASK-200: CLI Task\n\nBody prose",
    }
    proc = subprocess.run(cmd_create, input=json.dumps(create_payload), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    cr_receipt = json.loads(proc.stdout)

    task_file = tmp_path / "tasks" / "TASK-200.md"
    h0 = hashlib.sha256(task_file.read_bytes()).hexdigest()

    cmd_update = [
        sys.executable, "-m", "deltafuse.cli",
        "artifact", "update",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", "-",
        "--json",
    ]
    update_payload = {
        "request_id": "cli-req-up-1",
        "target": "tasks/TASK-200.md",
        "expected_sha256": h0,
        "patch": {"set": [{"path": "/kind", "value": "refactor"}]},
    }
    proc = subprocess.run(cmd_update, input=json.dumps(update_payload), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    up_receipt1 = json.loads(proc.stdout)
    assert up_receipt1["changed"] is True

    proc = subprocess.run(cmd_update, input=json.dumps(update_payload), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    up_receipt2 = json.loads(proc.stdout)
    assert up_receipt2["transaction_id"] == up_receipt1["transaction_id"]
    assert up_receipt2["changed"] is True

